from __future__ import annotations

import os
import re
from collections.abc import Iterator
from contextlib import contextmanager
import sqlite3
import time
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

from exif_tool import ExifTool, KeywordState
from utils import SUPPORTED_EXTS, dedupe_casefold, normalize_path


# SQLite commonly permits 999 bind variables. Keep path-set queries comfortably below
# that limit so supported builds with the default limit can index large workspaces.
_PATH_QUERY_BATCH_SIZE = 500
_INDEX_REFRESH_MAX_AGE_SECONDS = 24 * 60 * 60


def _normalize_root(root: str | Path) -> Path:
    return Path(root).resolve()


def resolve_index_root(
    paths: list[str | Path], preferred_root: str | Path | None = None
) -> Path | None:
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
                if all(
                    os.path.commonpath([str(pref), str(p)]) == str(pref)
                    for p in candidates
                ):
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


class DateQueryError(ValueError):
    """Raised when a ``date:`` search expression is not part of the grammar."""


@dataclass(frozen=True)
class DateSearch:
    start: str | None = None
    end_exclusive: str | None = None
    is_unknown: bool = False


_DATE_QUERY_HELP = "use YYYY, YYYY-MM, YYYY-MM-DD, YYYY-MM-DD..YYYY-MM-DD, or unknown"
_CAPTURE_DATE_PREFIX = re.compile(r"^(\d{4})[:-](\d{2})[:-](\d{2})(?:$|[ T])")


def _parse_calendar_day(value: str) -> date:
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise DateQueryError(_DATE_QUERY_HELP)
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise DateQueryError(_DATE_QUERY_HELP) from error


def _normalize_capture_date(value: str | None) -> str | None:
    if not value:
        return None
    match = _CAPTURE_DATE_PREFIX.match(value.strip())
    if match is None:
        return None
    try:
        return date(*map(int, match.groups())).isoformat()
    except ValueError:
        return None


def _capture_date_from_state(state: KeywordState) -> str | None:
    return _normalize_capture_date(state.date_original or state.date_create)


def _parse_date_search_term(term: str) -> DateSearch:
    term = term.strip()
    if term.casefold() == "unknown":
        return DateSearch(is_unknown=True)
    if ".." in term:
        endpoints = term.split("..")
        if len(endpoints) != 2:
            raise DateQueryError(_DATE_QUERY_HELP)
        start = _parse_calendar_day(endpoints[0])
        end = _parse_calendar_day(endpoints[1])
        if end < start:
            raise DateQueryError("range end must not be before range start")
        return DateSearch(start.isoformat(), (end + timedelta(days=1)).isoformat())
    if re.fullmatch(r"\d{4}", term):
        year = int(term)
        return DateSearch(f"{year:04}-01-01", f"{year + 1:04}-01-01")
    if re.fullmatch(r"\d{4}-\d{2}", term):
        year, month = map(int, term.split("-"))
        try:
            start = date(year, month, 1)
        except ValueError as error:
            raise DateQueryError(_DATE_QUERY_HELP) from error
        end = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
        return DateSearch(start.isoformat(), end.isoformat())
    day = _parse_calendar_day(term)
    return DateSearch(day.isoformat(), (day + timedelta(days=1)).isoformat())


def _date_search_from_query(query: str) -> DateSearch | None:
    query = query.strip()
    if not query.casefold().startswith("date:"):
        return None
    return _parse_date_search_term(query[5:])


def validate_search_query(query: str) -> None:
    """Raise ``DateQueryError`` when a date expression is not valid."""
    _date_search_from_query(query)


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

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        """Commit or roll back one connection, then always release its file handle."""
        conn = self._connect()
        try:
            yield conn
            conn.commit()
        except BaseException:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _ensure_schema(self, conn: sqlite3.Connection) -> None:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS photos(
              path TEXT PRIMARY KEY,
              mtime INTEGER NOT NULL,
              size INTEGER NOT NULL,
              date_taken TEXT,
              capture_date TEXT
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
        photo_columns = {
            str(row["name"])
            for row in conn.execute("PRAGMA table_info(photos)").fetchall()
        }
        migrated_capture_date = "capture_date" not in photo_columns
        if migrated_capture_date:
            conn.execute("ALTER TABLE photos ADD COLUMN capture_date TEXT")
            for row in conn.execute(
                "SELECT path, date_taken FROM photos WHERE capture_date IS NULL"
            ):
                conn.execute(
                    "UPDATE photos SET capture_date = ? WHERE path = ?",
                    (_normalize_capture_date(row["date_taken"]), row["path"]),
                )

        conn.execute("CREATE INDEX IF NOT EXISTS idx_tags_tag ON tags(tag)")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_photos_date_taken ON photos(date_taken)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_photos_capture_date ON photos(capture_date)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_photo_tags_tag_id ON photo_tags(tag_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_photo_tags_photo_path ON photo_tags(photo_path)"
        )

    def is_initialized(self) -> bool:
        with self._connection() as conn:
            row = conn.execute(
                "SELECT value FROM meta WHERE key = ?", ("initialized",)
            ).fetchone()
            return bool(row and str(row[0]) == "1")

    def last_index_refresh(self) -> int | None:
        """Return the Unix timestamp of the latest successful root synchronization."""
        with self._connection() as conn:
            row = conn.execute(
                "SELECT value FROM meta WHERE key = ?", ("last_index_scan",)
            ).fetchone()
        if row is None:
            return None
        try:
            return int(str(row[0]))
        except ValueError:
            return None

    def is_refresh_stale(
        self,
        *,
        now: float | None = None,
        max_age_seconds: int = _INDEX_REFRESH_MAX_AGE_SECONDS,
    ) -> bool:
        """Return whether this root needs a full metadata synchronization."""
        last_refresh = self.last_index_refresh()
        if last_refresh is None:
            return True
        current_time = time.time() if now is None else now
        return current_time - last_refresh >= max_age_seconds

    def has_photos(self, paths: list[str]) -> set[str]:
        normalized = [normalize_path(p) for p in paths]
        if not normalized:
            return set()
        with self._connection() as conn:
            found_paths: set[str] = set()
            for offset in range(0, len(normalized), _PATH_QUERY_BATCH_SIZE):
                batch = normalized[offset : offset + _PATH_QUERY_BATCH_SIZE]
                placeholders = ",".join("?" for _ in batch)
                rows = conn.execute(
                    f"SELECT path FROM photos WHERE path IN ({placeholders})",
                    batch,
                ).fetchall()
                found_paths.update(str(row[0]) for row in rows)
            return found_paths

    def _photo_rows(
        self, conn: sqlite3.Connection, paths: list[str]
    ) -> dict[str, sqlite3.Row]:
        if not paths:
            return {}
        rows_by_path: dict[str, sqlite3.Row] = {}
        for offset in range(0, len(paths), _PATH_QUERY_BATCH_SIZE):
            batch = paths[offset : offset + _PATH_QUERY_BATCH_SIZE]
            placeholders = ",".join("?" for _ in batch)
            rows = conn.execute(
                f"SELECT path, mtime, size, date_taken FROM photos WHERE path IN ({placeholders})",
                batch,
            ).fetchall()
            rows_by_path.update({row["path"]: row for row in rows})
        return rows_by_path

    def _tag_id(self, conn: sqlite3.Connection, tag: str) -> int:
        tag = tag.strip()
        conn.execute("INSERT OR IGNORE INTO tags(tag) VALUES (?)", (tag,))
        row = conn.execute("SELECT id FROM tags WHERE tag = ?", (tag,)).fetchone()
        if row is None:
            raise RuntimeError(f"Failed to resolve tag id for {tag!r}")
        return int(row[0])

    def load_known_tags(self) -> set[str]:
        with self._connection() as conn:
            rows = conn.execute(
                "SELECT tag FROM tags ORDER BY tag COLLATE NOCASE"
            ).fetchall()
            return {str(row[0]) for row in rows}

    def load_tags_for_photo(self, photo_path: str) -> list[str]:
        photo_path = normalize_path(photo_path)
        with self._connection() as conn:
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
        with self._connection() as conn:
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
        with self._connection() as conn:
            if qlower.startswith("tag:"):
                term = query[4:].strip()
                return self.load_photos_for_tag(term) if term else []

            if qlower.startswith("date:"):
                date_search = _date_search_from_query(query)
                if date_search is None:
                    raise AssertionError("date query was not recognized")
                if date_search.is_unknown:
                    rows = conn.execute(
                        "SELECT path FROM photos WHERE capture_date IS NULL ORDER BY path"
                    ).fetchall()
                else:
                    rows = conn.execute(
                        """
                        SELECT path FROM photos
                        WHERE capture_date >= ? AND capture_date < ?
                        ORDER BY path
                        """,
                        (date_search.start, date_search.end_exclusive),
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
        with self._connection() as conn:
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

    def upsert_state(
        self, conn: sqlite3.Connection, photo_path: str, state: KeywordState
    ) -> None:
        photo_path = normalize_path(photo_path)
        stat = Path(photo_path).stat()
        conn.execute(
            """
            INSERT INTO photos(path, mtime, size, date_taken, capture_date)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(path) DO UPDATE SET
              mtime=excluded.mtime,
              size=excluded.size,
              date_taken=excluded.date_taken,
              capture_date=excluded.capture_date
            """,
            (
                photo_path,
                int(stat.st_mtime),
                int(stat.st_size),
                _date_taken_from_state(state),
                _capture_date_from_state(state),
            ),
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
        with self._connection() as conn:
            with conn:
                for photo_path, state in updated_states.items():
                    self.upsert_state(conn, photo_path, state)

    def mark_initialized(self) -> None:
        with self._connection() as conn:
            with conn:
                conn.execute(
                    "INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)",
                    ("initialized", "1"),
                )

    def remove_photo(self, photo_path: str) -> bool:
        """Remove one indexed photo and any tag vocabulary it leaves unused."""
        normalized_path = normalize_path(photo_path)
        with self._connection() as conn:
            cursor = conn.execute(
                "DELETE FROM photos WHERE path = ?", (normalized_path,)
            )
            self._prune_orphan_tags(conn)
            return cursor.rowcount > 0

    def sync_root(self, exif: ExifTool, recursive: bool = True) -> IndexSyncResult:
        del recursive
        paths = [
            str(path)
            for path in self.root.rglob("*")
            if path.is_file() and path.suffix.lower() in SUPPORTED_EXTS
        ]
        return self._sync_paths(exif, paths, force=True, deletion_directory=None)

    def sync_directory(self, exif: ExifTool, directory: str | Path) -> IndexSyncResult:
        """Synchronize direct supported files in one directory without recursion."""
        scope = Path(directory).resolve()
        paths = (
            [
                str(path)
                for path in scope.iterdir()
                if path.is_file() and path.suffix.lower() in SUPPORTED_EXTS
            ]
            if scope.is_dir()
            else []
        )
        return self._sync_paths(exif, paths, force=True, deletion_directory=scope)

    def sync_paths(
        self, exif: ExifTool, paths: list[str], *, force: bool = False
    ) -> IndexSyncResult:
        """Synchronize the supplied full-root discovery result without traversal."""
        return self._sync_paths(exif, paths, force=force, deletion_directory=None)

    def _sync_paths(
        self,
        exif: ExifTool,
        paths: list[str],
        *,
        force: bool,
        deletion_directory: Path | None,
    ) -> IndexSyncResult:
        current_paths = [
            normalize_path(path)
            for path in paths
            if Path(path).suffix.lower() in SUPPORTED_EXTS
        ]
        current_set = set(current_paths)
        updated_count = 0

        with self._connection() as conn:
            existing = self._photo_rows(conn, current_paths)
            changed: list[str] = []
            for photo_path in current_paths:
                try:
                    stat = Path(photo_path).stat()
                except FileNotFoundError:
                    continue
                row = existing.get(photo_path)
                if (
                    force
                    or row is None
                    or int(row["mtime"]) != int(stat.st_mtime)
                    or int(row["size"]) != int(stat.st_size)
                ):
                    changed.append(photo_path)

            if changed:
                states = exif.read_keywords_many(changed)
                for photo_path in changed:
                    state = states.get(photo_path)
                    if state is None:
                        continue
                    self.upsert_state(conn, photo_path, state)
                    updated_count += 1

            db_paths = {
                str(row[0])
                for row in conn.execute("SELECT path FROM photos").fetchall()
            }
            if deletion_directory is None:
                candidates = db_paths
            else:
                candidates = {
                    photo_path
                    for photo_path in db_paths
                    if Path(photo_path).parent == deletion_directory
                }
            missing = sorted(candidates - current_set)
            for photo_path in missing:
                conn.execute("DELETE FROM photos WHERE path = ?", (photo_path,))
            self._prune_orphan_tags(conn)

            if deletion_directory is None:
                conn.execute(
                    "INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)",
                    ("last_index_scan", str(int(time.time()))),
                )
            conn.execute(
                "INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)",
                ("initialized", "1"),
            )

        return IndexSyncResult(
            root=str(self.root),
            scanned_count=len(current_paths),
            updated_count=updated_count,
            deleted_count=len(missing),
            known_tag_count=len(self.load_known_tags()),
        )

    def _prune_orphan_tags(self, conn: sqlite3.Connection) -> None:
        conn.execute(
            "DELETE FROM tags WHERE NOT EXISTS ("
            "SELECT 1 FROM photo_tags WHERE photo_tags.tag_id = tags.id)"
        )
