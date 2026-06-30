from __future__ import annotations

import os
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path

from exif_tool import ExifTool, KeywordState
from utils import SUPPORTED_EXTS, dedupe_casefold, normalize_path


def _normalize_root(root: str | Path) -> Path:
    return Path(root).resolve()


def resolve_index_root(paths: list[str | Path], preferred_root: str | Path | None = None) -> Path | None:
    candidates = [Path(p).resolve() for p in paths if str(p).strip()]
    if not candidates:
        if preferred_root is not None:
            pref = _normalize_root(preferred_root)
            return pref if pref.exists() else None
        return None

    if preferred_root is not None:
        pref = _normalize_root(preferred_root)
        if pref.exists():
            try:
                if all(os.path.commonpath([str(pref), str(p)]) == str(pref) for p in candidates):
                    return pref
            except Exception:
                pass

    try:
        common = Path(os.path.commonpath([str(p) for p in candidates])).resolve()
    except Exception:
        common = candidates[0].parent if candidates[0].is_file() else candidates[0]
    return common.parent if common.is_file() else common


def _date_taken_from_state(state: KeywordState) -> str:
    return state.date_display or ""


@dataclass(frozen=True)
class IndexSyncResult:
    root: str
    scanned_count: int
    updated_count: int
    deleted_count: int
    known_tag_count: int


class PhotoIndex:
    def __init__(self, root: str | Path) -> None:
        self.root = _normalize_root(root)
        self.db_path = self.root / ".tagger" / "index.sqlite"

    def _connect(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")
        conn.execute("PRAGMA temp_store = MEMORY")
        self._ensure_schema(conn)
        return conn

    def _ensure_schema(self, conn: sqlite3.Connection) -> None:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS photos(
              path TEXT PRIMARY KEY,
              mtime INTEGER NOT NULL,
              size INTEGER NOT NULL,
              date_taken TEXT
            );

            CREATE TABLE IF NOT EXISTS tags(
              id INTEGER PRIMARY KEY,
              tag TEXT NOT NULL COLLATE NOCASE UNIQUE
            );

            CREATE TABLE IF NOT EXISTS photo_tags(
              photo_path TEXT NOT NULL,
              tag_id INTEGER NOT NULL,
              PRIMARY KEY(photo_path, tag_id),
              FOREIGN KEY(photo_path) REFERENCES photos(path) ON DELETE CASCADE,
              FOREIGN KEY(tag_id) REFERENCES tags(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS meta(
              key TEXT PRIMARY KEY,
              value TEXT NOT NULL
            );
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_tags_tag ON tags(tag)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_photos_date_taken ON photos(date_taken)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_photo_tags_tag_id ON photo_tags(tag_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_photo_tags_photo_path ON photo_tags(photo_path)")

    def is_initialized(self) -> bool:
        with self._connect() as conn:
            row = conn.execute("SELECT value FROM meta WHERE key = ?", ("initialized",)).fetchone()
            return bool(row and str(row[0]) == "1")

    def has_photos(self, paths: list[str]) -> set[str]:
        normalized = [normalize_path(p) for p in paths]
        if not normalized:
            return set()
        with self._connect() as conn:
            placeholders = ",".join("?" for _ in normalized)
            rows = conn.execute(
                f"SELECT path FROM photos WHERE path IN ({placeholders})",
                normalized,
            ).fetchall()
            return {str(row[0]) for row in rows}

    def _photo_rows(self, conn: sqlite3.Connection, paths: list[str]) -> dict[str, sqlite3.Row]:
        if not paths:
            return {}
        placeholders = ",".join("?" for _ in paths)
        rows = conn.execute(
            f"SELECT path, mtime, size, date_taken FROM photos WHERE path IN ({placeholders})",
            paths,
        ).fetchall()
        return {row["path"]: row for row in rows}

    def _tag_id(self, conn: sqlite3.Connection, tag: str) -> int:
        tag = tag.strip()
        conn.execute("INSERT OR IGNORE INTO tags(tag) VALUES (?)", (tag,))
        row = conn.execute("SELECT id FROM tags WHERE tag = ?", (tag,)).fetchone()
        if row is None:
            raise RuntimeError(f"Failed to resolve tag id for {tag!r}")
        return int(row[0])

    def load_known_tags(self) -> set[str]:
        with self._connect() as conn:
            rows = conn.execute("SELECT tag FROM tags ORDER BY tag COLLATE NOCASE").fetchall()
            return {str(row[0]) for row in rows}

    def load_tags_for_photo(self, photo_path: str) -> list[str]:
        photo_path = normalize_path(photo_path)
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT t.tag
                FROM tags t
                JOIN photo_tags pt ON pt.tag_id = t.id
                WHERE pt.photo_path = ?
                ORDER BY t.tag COLLATE NOCASE
                """,
                (photo_path,),
            ).fetchall()
            return [str(row[0]) for row in rows]

    def load_photos_for_tag(self, tag: str) -> list[str]:
        tag = tag.strip()
        if not tag:
            return []
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT p.path
                FROM photos p
                JOIN photo_tags pt ON pt.photo_path = p.path
                JOIN tags t ON t.id = pt.tag_id
                WHERE t.tag = ?
                ORDER BY p.path
                """,
                (tag,),
            ).fetchall()
            return [str(row[0]) for row in rows]

    def _escape_like(self, value: str) -> str:
        return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")

    def search_photos(self, query: str) -> list[str]:
        query = query.strip()
        if not query:
            return []

        qlower = query.lower()
        with self._connect() as conn:
            if qlower.startswith("tag:"):
                term = query[4:].strip()
                return self.load_photos_for_tag(term) if term else []

            if qlower.startswith("date:"):
                term = query[5:].strip()
                if not term:
                    return []
                rows = conn.execute(
                    "SELECT path FROM photos WHERE date_taken LIKE ? ESCAPE '\\' ORDER BY path",
                    (f"%{self._escape_like(term)}%",),
                ).fetchall()
                return [str(row[0]) for row in rows]

            exact = self.load_photos_for_tag(query)
            if exact:
                return exact

            rows = conn.execute(
                """
                SELECT DISTINCT p.path
                FROM photos p
                JOIN photo_tags pt ON pt.photo_path = p.path
                JOIN tags t ON t.id = pt.tag_id
                WHERE t.tag LIKE ? ESCAPE '\\'
                ORDER BY p.path
                """,
                (f"%{self._escape_like(query)}%",),
            ).fetchall()
            return [str(row[0]) for row in rows]

    def load_tags_for_root(self) -> set[str]:
        with self._connect() as conn:
            prefix = str(self.root) + os.sep
            rows = conn.execute(
                """
                SELECT DISTINCT t.tag
                FROM tags t
                JOIN photo_tags pt ON pt.tag_id = t.id
                JOIN photos p ON p.path = pt.photo_path
                WHERE instr(p.path, ?) = 1
                ORDER BY t.tag COLLATE NOCASE
                """,
                (prefix,),
            ).fetchall()
            return {str(row[0]) for row in rows}

    def upsert_state(self, conn: sqlite3.Connection, photo_path: str, state: KeywordState) -> None:
        photo_path = normalize_path(photo_path)
        stat = Path(photo_path).stat()
        conn.execute(
            """
            INSERT INTO photos(path, mtime, size, date_taken)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(path) DO UPDATE SET
              mtime=excluded.mtime,
              size=excluded.size,
              date_taken=excluded.date_taken
            """,
            (photo_path, int(stat.st_mtime), int(stat.st_size), _date_taken_from_state(state)),
        )
        conn.execute("DELETE FROM photo_tags WHERE photo_path = ?", (photo_path,))
        tags = dedupe_casefold(state.merged)
        for tag in tags:
            tag_id = self._tag_id(conn, tag)
            conn.execute(
                "INSERT OR IGNORE INTO photo_tags(photo_path, tag_id) VALUES (?, ?)",
                (photo_path, tag_id),
            )

    def update_states(self, updated_states: dict[str, KeywordState]) -> None:
        if not updated_states:
            return
        with self._connect() as conn:
            with conn:
                for photo_path, state in updated_states.items():
                    self.upsert_state(conn, photo_path, state)

    def mark_initialized(self) -> None:
        with self._connect() as conn:
            with conn:
                conn.execute(
                    "INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)",
                    ("initialized", "1"),
                )

    def sync_root(self, exif: ExifTool, recursive: bool = True) -> IndexSyncResult:
        root = self.root
        current_paths = [
            normalize_path(str(p))
            for p in root.rglob("*")
            if p.is_file() and p.suffix.lower() in SUPPORTED_EXTS
        ]
        current_set = set(current_paths)

        scanned_count = len(current_paths)
        updated_count = 0

        with self._connect() as conn:
            existing = self._photo_rows(conn, current_paths)
            changed: list[str] = []

            for photo_path in current_paths:
                try:
                    stat = Path(photo_path).stat()
                except FileNotFoundError:
                    continue
                row = existing.get(photo_path)
                if row is None:
                    changed.append(photo_path)
                    continue
                if int(row["mtime"]) != int(stat.st_mtime) or int(row["size"]) != int(stat.st_size):
                    changed.append(photo_path)

            if changed:
                states = exif.read_keywords_many(changed)
                with conn:
                    for photo_path in changed:
                        state = states.get(photo_path)
                        if state is None:
                            continue
                        self.upsert_state(conn, photo_path, state)
                        updated_count += 1

            db_rows = conn.execute("SELECT path FROM photos").fetchall()
            db_paths = {str(row[0]) for row in db_rows}
            missing = sorted(db_paths - current_set)
            deleted_count = 0
            if missing:
                with conn:
                    for photo_path in missing:
                        conn.execute("DELETE FROM photos WHERE path = ?", (photo_path,))
                        deleted_count += 1

            conn.execute(
                "INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)",
                ("last_index_scan", str(int(time.time()))),
            )
            conn.execute(
                "INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)",
                ("initialized", "1"),
            )

        return IndexSyncResult(
            root=str(root),
            scanned_count=scanned_count,
            updated_count=updated_count,
            deleted_count=deleted_count,
            known_tag_count=len(self.load_known_tags()),
        )
