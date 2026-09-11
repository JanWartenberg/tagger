#!/usr/bin/env python3
"""Move TAGGER's per-folder SQLite index after a photo-folder relocation.

The image metadata is not changed. Only cached absolute paths in the index are
rewritten; the tags and all other index data remain untouched.
"""

from __future__ import annotations

import argparse
import sqlite3
from datetime import datetime
from pathlib import Path
from uuid import uuid4


INDEX_FILENAME = "index.sqlite"


def _index_path(root: Path) -> Path:
    return root / ".tagger" / INDEX_FILENAME


def _relocated_path(path: str, old_root: Path, new_root: Path) -> str | None:
    try:
        relative = Path(path).relative_to(old_root)
    except ValueError:
        return None
    return str(new_root / relative)


def _backup_database(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Reserve the destination exclusively: never overwrite an existing backup
    # (or a target created after the initial migration checks).
    with destination.open("xb"):
        pass
    try:
        source_conn = sqlite3.connect(source)
        try:
            destination_conn = sqlite3.connect(destination)
            try:
                source_conn.backup(destination_conn)
            finally:
                destination_conn.close()
        finally:
            source_conn.close()
    except BaseException:
        destination.unlink()
        raise


def migrate(
    old_root: Path,
    new_root: Path,
    *,
    database: Path | None = None,
    dry_run: bool = False,
) -> tuple[int, int]:
    old_root = old_root.resolve()
    new_root = new_root.resolve()
    source_db = (database or _index_path(old_root)).resolve()
    target_db = _index_path(new_root).resolve()

    if database is None and not old_root.exists():
        raise SystemExit(f"Old root does not exist: {old_root}")
    if not new_root.is_dir():
        raise SystemExit(f"New root is not a directory: {new_root}")
    if not source_db.is_file():
        raise SystemExit(f"Index database not found: {source_db}")
    if source_db != target_db and target_db.exists() and not dry_run:
        raise SystemExit(
            f"Target database already exists: {target_db}\n"
            "Move it away or remove it after making a backup."
        )

    conn = sqlite3.connect(source_db)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute("SELECT path FROM photos").fetchall()
        replacements = {
            str(row["path"]): _relocated_path(str(row["path"]), old_root, new_root)
            for row in rows
        }
        replacements = {
            old: new for old, new in replacements.items() if new is not None
        }
        target_paths = {
            str(row[0]) for row in conn.execute("SELECT path FROM photos").fetchall()
        }
        collisions = {
            new
            for old, new in replacements.items()
            if new in target_paths and new != old
        }
        if collisions:
            raise SystemExit(
                "Migration would overwrite existing indexed paths: "
                + ", ".join(sorted(collisions))
            )

        if dry_run:
            return len(replacements), len(rows)

        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup = target_db.with_name(
            f"{target_db.name}.before-migration-{timestamp}-{uuid4().hex}"
        )
        if source_db == target_db:
            _backup_database(source_db, backup)
        else:
            _backup_database(source_db, target_db)
            conn.close()
            conn = sqlite3.connect(target_db)
            conn.row_factory = sqlite3.Row

        with conn:
            # Update children first because photo_tags.photo_path references
            # photos.path and the schema intentionally has no ON UPDATE CASCADE.
            for old, new in replacements.items():
                conn.execute(
                    "UPDATE photo_tags SET photo_path = ? WHERE photo_path = ?",
                    (new, old),
                )
                conn.execute("UPDATE photos SET path = ? WHERE path = ?", (new, old))
            # Older indexes predate refresh checkpoints. Clear only tables that
            # exist, without running application schema upgrades on cached tags.
            tables = {
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                )
            }
            for table in (
                "refresh_directories",
                "refresh_paths",
                "refresh_checkpoint",
            ):
                if table in tables:
                    conn.execute(f"DELETE FROM {table}")
        return len(replacements), len(rows)
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("old_root", type=Path, help="Previous photo-folder path")
    parser.add_argument("new_root", type=Path, help="Current photo-folder path")
    parser.add_argument(
        "--database",
        type=Path,
        help="Source index.sqlite, useful when the old folder no longer exists",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Only report what would be changed"
    )
    args = parser.parse_args()

    changed, total = migrate(
        args.old_root,
        args.new_root,
        database=args.database,
        dry_run=args.dry_run,
    )
    print(f"Index entries: {total}; paths to relocate: {changed}")
    if args.dry_run:
        print("Dry run: no files changed.")
    else:
        source_db = (args.database or _index_path(args.old_root)).resolve()
        if source_db == _index_path(args.new_root).resolve():
            print("Migration complete. A .before-migration backup was created.")
        else:
            print(f"Migration complete. Source database preserved at: {source_db}")


if __name__ == "__main__":
    main()
