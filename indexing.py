from __future__ import annotations

import os
import re
from collections.abc import Iterator
from contextlib import contextmanager
import sqlite3
import time
import unicodedata
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

from exif_tool import ExifTool, KeywordState
from utils import SUPPORTED_EXTS, dedupe_casefold, normalize_path


# SQLite commonly permits 999 bind variables. Keep path-set queries comfortably below
# that limit so supported builds with the default limit can index large workspaces.
_PATH_QUERY_BATCH_SIZE = 500
_INDEX_REFRESH_MAX_AGE_SECONDS = 24 * 60 * 60
_REFRESH_RESUME_MAX_AGE_SECONDS = 60 * 60
_REFRESH_PATH_BATCH_SIZE = 1_000
_REFRESH_EXIF_SUBGROUP_SIZE = 200
_KEYWORD_INDEX_VERSION = "canonical-iptc-v1"
_KEYWORD_INDEX_VERSION_REBUILDING = f"{_KEYWORD_INDEX_VERSION}-rebuilding"
_KEYWORD_INDEX_VERSION_META_KEY = "keyword_index_version"


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


def _split_tag_and_date_query(query: str) -> tuple[str, str] | None:
    """Return the tag and date terms emitted by the separate filter controls."""
    if not query.casefold().startswith("tag:"):
        return None
    marker = " date:"
    split_at = query.casefold().rfind(marker)
    if split_at < 4:
        return None
    tag_term = query[4:split_at].strip()
    date_term = query[split_at + len(marker) :].strip()
    return (tag_term, date_term) if tag_term and date_term else None


def validate_search_query(query: str) -> None:
    """Raise ``DateQueryError`` when a date expression is not valid."""
    compound = _split_tag_and_date_query(query.strip())
    if compound is not None:
        _parse_date_search_term(compound[1])
        return
    _date_search_from_query(query)


@dataclass(frozen=True)
class IndexSyncResult:
    root: str
    scanned_count: int
    updated_count: int
    deleted_count: int
    known_tag_count: int


@dataclass(frozen=True)
class IptcEmptyIndexResult:
    """SQLite-derived IPTC-empty candidates and their readability state."""

    paths: tuple[str, ...]
    unknown_paths: frozenset[str]


@dataclass(frozen=True)
class IndexRefreshProgress:
    """A committed, resumable refresh checkpoint between index chunks."""

    root: str
    phase: str
    discovered_count: int
    indexed_count: int
    resumed: bool = False
    complete: bool = False


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
              capture_date TEXT,
              iptc_readable INTEGER NOT NULL DEFAULT 0
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

            CREATE TABLE IF NOT EXISTS refresh_checkpoint(
              singleton INTEGER PRIMARY KEY CHECK(singleton = 1),
              phase TEXT NOT NULL,
              started_at INTEGER NOT NULL,
              discovered_count INTEGER NOT NULL,
              indexed_count INTEGER NOT NULL,
              updated_count INTEGER NOT NULL,
              deleted_count INTEGER NOT NULL,
              resumed INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS refresh_directories(
              path TEXT PRIMARY KEY
            );

            CREATE TABLE IF NOT EXISTS refresh_paths(
              path TEXT PRIMARY KEY
            );
            """
        )
        refresh_columns = {
            str(row["name"])
            for row in conn.execute("PRAGMA table_info(refresh_checkpoint)").fetchall()
        }
        if "resumed" not in refresh_columns:
            conn.execute(
                "ALTER TABLE refresh_checkpoint "
                "ADD COLUMN resumed INTEGER NOT NULL DEFAULT 0"
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
        if "iptc_readable" not in photo_columns:
            # Existing rows cannot establish whether an absent tag is readable.
            # A later index update replaces this conservative unknown state.
            conn.execute(
                "ALTER TABLE photos ADD COLUMN iptc_readable INTEGER NOT NULL DEFAULT 0"
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
        self._ensure_keyword_index_version(conn)

    def _keyword_index_version(self, conn: sqlite3.Connection) -> str | None:
        row = conn.execute(
            "SELECT value FROM meta WHERE key = ?", (_KEYWORD_INDEX_VERSION_META_KEY,)
        ).fetchone()
        return str(row[0]) if row is not None else None

    def _ensure_keyword_index_version(self, conn: sqlite3.Connection) -> None:
        """Invalidate legacy merged-keyword facts exactly once per index root."""
        version = self._keyword_index_version(conn)
        if version in {_KEYWORD_INDEX_VERSION, _KEYWORD_INDEX_VERSION_REBUILDING}:
            return
        has_legacy_facts = any(
            conn.execute(f"SELECT 1 FROM {table} LIMIT 1").fetchone() is not None
            for table in ("photos", "tags", "photo_tags")
        )
        if not has_legacy_facts:
            conn.execute(
                "INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)",
                (_KEYWORD_INDEX_VERSION_META_KEY, _KEYWORD_INDEX_VERSION),
            )
            return

        # A merged row cannot be projected to IPTC without rereading the file.
        # Keep photo rows for their paths and date data, but make all tag reads
        # empty until a full-root background rebuild supplies canonical facts.
        conn.execute("DELETE FROM photo_tags")
        conn.execute("DELETE FROM tags")
        conn.execute(
            "INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)",
            (_KEYWORD_INDEX_VERSION_META_KEY, _KEYWORD_INDEX_VERSION_REBUILDING),
        )
        conn.execute(
            "INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)",
            ("initialized", "0"),
        )
        conn.execute("DELETE FROM meta WHERE key = ?", ("last_index_scan",))

    def _keyword_index_rebuild_pending(self, conn: sqlite3.Connection) -> bool:
        return self._keyword_index_version(conn) == _KEYWORD_INDEX_VERSION_REBUILDING

    def needs_keyword_index_rebuild(self) -> bool:
        with self._connection() as conn:
            return self._keyword_index_rebuild_pending(conn)

    def is_initialized(self) -> bool:
        with self._connection() as conn:
            initialized = conn.execute(
                "SELECT value FROM meta WHERE key = ?", ("initialized",)
            ).fetchone()
            return bool(
                initialized
                and str(initialized[0]) == "1"
                and self._keyword_index_version(conn) == _KEYWORD_INDEX_VERSION
            )

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
        current_time = time.time() if now is None else now
        checkpoint_started = self._refresh_checkpoint_started()
        if checkpoint_started is not None:
            # An interrupted run is resumed for an hour; an older checkpoint is
            # discarded and replaced by a new run when the root becomes active.
            return True
        last_refresh = self.last_index_refresh()
        if last_refresh is None:
            return True
        return current_time - last_refresh >= max_age_seconds

    def _refresh_checkpoint_started(self) -> int | None:
        with self._connection() as conn:
            row = conn.execute(
                "SELECT started_at FROM refresh_checkpoint WHERE singleton = 1"
            ).fetchone()
        return int(row[0]) if row is not None else None

    def cancel_refresh(self) -> bool:
        """Discard unfinished refresh recovery state for this index root."""
        with self._connection() as conn:
            present = conn.execute(
                "SELECT 1 FROM refresh_checkpoint WHERE singleton = 1"
            ).fetchone()
            conn.execute("DELETE FROM refresh_directories")
            conn.execute("DELETE FROM refresh_paths")
            conn.execute("DELETE FROM refresh_checkpoint")
        return present is not None

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

    def load_iptc_empty_photos(self) -> IptcEmptyIndexResult:
        """Return empty canonical-IPTC rows, retaining unreadable candidates."""
        with self._connection() as conn:
            rows = conn.execute(
                """
                SELECT p.path, p.iptc_readable
                FROM photos p
                WHERE NOT EXISTS (
                  SELECT 1 FROM photo_tags pt WHERE pt.photo_path = p.path
                )
                ORDER BY p.path
                """
            ).fetchall()
        existing_rows = []
        for row in rows:
            try:
                if Path(str(row["path"])).is_file():
                    existing_rows.append(row)
            except OSError:
                continue
        paths = tuple(str(row["path"]) for row in existing_rows)
        return IptcEmptyIndexResult(
            paths,
            frozenset(
                str(row["path"]) for row in existing_rows if not row["iptc_readable"]
            ),
        )

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

        compound = _split_tag_and_date_query(query)
        if compound is not None:
            tag_term, date_term = compound
            tag_paths = set(self.search_photos(tag_term))
            date_paths = self.search_photos(f"date:{date_term}")
            return [path for path in date_paths if path in tag_paths]

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
            INSERT INTO photos(
              path, mtime, size, date_taken, capture_date, iptc_readable
            ) VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(path) DO UPDATE SET
              mtime=excluded.mtime,
              size=excluded.size,
              date_taken=excluded.date_taken,
              capture_date=excluded.capture_date,
              iptc_readable=excluded.iptc_readable
            """,
            (
                photo_path,
                int(stat.st_mtime),
                int(stat.st_size),
                _date_taken_from_state(state),
                _capture_date_from_state(state),
                int(state.iptc_readable),
            ),
        )
        conn.execute("DELETE FROM photo_tags WHERE photo_path = ?", (photo_path,))
        tags = self._canonical_iptc_tags(state)
        for tag in tags:
            tag_id = self._tag_id(conn, tag)
            conn.execute(
                "INSERT OR IGNORE INTO photo_tags(photo_path, tag_id) VALUES (?, ?)",
                (photo_path, tag_id),
            )

    def _canonical_iptc_tags(self, state: KeywordState) -> list[str]:
        """Project one readable metadata state to canonical keyword facts."""
        if not state.iptc_readable:
            return []
        return dedupe_casefold(
            [unicodedata.normalize("NFC", tag.strip()) for tag in state.iptc]
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

    def refresh_step(
        self, exif: ExifTool, *, restart: bool = False
    ) -> IndexRefreshProgress | IndexSyncResult:
        try:
            return self._refresh_step(exif, restart=restart)
        except Exception:
            # A terminal subgroup failure must not leave a resumable checkpoint;
            # earlier committed chunks remain normal index data.
            self.cancel_refresh()
            raise

    def _refresh_step(
        self, exif: ExifTool, *, restart: bool = False
    ) -> IndexRefreshProgress | IndexSyncResult:
        """Commit one bounded full-root refresh chunk.

        The checkpoint stores only directories yet to walk and photos yet to index.
        Completed paths live exclusively in the normal index, so a restart does not
        create a second durable manifest of the root.
        """
        now = int(time.time())
        resumed = False
        with self._connection() as conn:
            checkpoint = conn.execute(
                "SELECT * FROM refresh_checkpoint WHERE singleton = 1"
            ).fetchone()
            if checkpoint is not None and (
                restart
                or now - int(checkpoint["started_at"])
                >= _REFRESH_RESUME_MAX_AGE_SECONDS
            ):
                self._clear_refresh_checkpoint(conn)
                checkpoint = None
            if checkpoint is None:
                conn.execute(
                    """
                    INSERT INTO refresh_checkpoint(
                      singleton, phase, started_at, discovered_count, indexed_count,
                      updated_count, deleted_count
                    ) VALUES (1, 'discovering', ?, 0, 0, 0, 0)
                    """,
                    (now,),
                )
                conn.execute(
                    "INSERT INTO refresh_directories(path) VALUES (?)",
                    (str(self.root),),
                )
            else:
                resumed = not bool(checkpoint["resumed"])
                if resumed:
                    conn.execute(
                        "UPDATE refresh_checkpoint SET resumed = 1 WHERE singleton = 1"
                    )

            phase = str(
                conn.execute(
                    "SELECT phase FROM refresh_checkpoint WHERE singleton = 1"
                ).fetchone()[0]
            )
            if phase == "discovering":
                paths, discovered = self._take_refresh_path_batch(conn)
                if paths:
                    updated, deleted, indexed = self._index_refresh_paths(
                        conn, exif, paths
                    )
                    conn.execute(
                        """
                        UPDATE refresh_checkpoint
                        SET discovered_count = discovered_count + ?,
                            indexed_count = indexed_count + ?,
                            updated_count = updated_count + ?,
                            deleted_count = deleted_count + ?
                        WHERE singleton = 1
                        """,
                        (discovered, indexed, updated, deleted),
                    )
                else:
                    conn.execute(
                        "UPDATE refresh_checkpoint SET phase = 'reconciling' "
                        "WHERE singleton = 1"
                    )

            checkpoint = conn.execute(
                "SELECT * FROM refresh_checkpoint WHERE singleton = 1"
            ).fetchone()
            if str(checkpoint["phase"]) == "discovering":
                return IndexRefreshProgress(
                    root=str(self.root),
                    phase="discovering",
                    discovered_count=int(checkpoint["discovered_count"]),
                    indexed_count=int(checkpoint["indexed_count"]),
                    resumed=resumed,
                )
            if phase == "discovering":
                return IndexRefreshProgress(
                    root=str(self.root),
                    phase="reconciling",
                    discovered_count=int(checkpoint["discovered_count"]),
                    indexed_count=int(checkpoint["indexed_count"]),
                    resumed=resumed,
                )

        # Reconciliation deliberately happens once, after streamed discovery.  It
        # observes additions, removals, and mtime/size changes made during the run.
        paths = [
            str(path)
            for path in self.root.rglob("*")
            if path.is_file() and path.suffix.lower() in SUPPORTED_EXTS
        ]
        reconciled = self._sync_paths(
            exif,
            paths,
            force=False,
            deletion_directory=None,
            force_migration=False,
        )
        with self._connection() as conn:
            checkpoint = conn.execute(
                "SELECT * FROM refresh_checkpoint WHERE singleton = 1"
            ).fetchone()
            if checkpoint is None:
                # Cancellation can run between a queued reconciliation and this
                # completion; retain the committed index but report its result.
                return reconciled
            result = IndexSyncResult(
                root=str(self.root),
                scanned_count=reconciled.scanned_count,
                updated_count=int(checkpoint["updated_count"])
                + reconciled.updated_count,
                deleted_count=int(checkpoint["deleted_count"])
                + reconciled.deleted_count,
                known_tag_count=reconciled.known_tag_count,
            )
            self._clear_refresh_checkpoint(conn)
            return result

    def _clear_refresh_checkpoint(self, conn: sqlite3.Connection) -> None:
        conn.execute("DELETE FROM refresh_directories")
        conn.execute("DELETE FROM refresh_paths")
        conn.execute("DELETE FROM refresh_checkpoint")

    def _take_refresh_path_batch(
        self, conn: sqlite3.Connection
    ) -> tuple[list[str], int]:
        """Stream directories into one bounded, durable pending-photo batch."""
        start = time.monotonic()
        discovered = 0
        while True:
            rows = conn.execute(
                "SELECT path FROM refresh_paths ORDER BY path LIMIT ?",
                (_REFRESH_PATH_BATCH_SIZE,),
            ).fetchall()
            if len(rows) >= _REFRESH_PATH_BATCH_SIZE:
                break
            directory = conn.execute(
                "SELECT path FROM refresh_directories ORDER BY path LIMIT 1"
            ).fetchone()
            if directory is None or time.monotonic() - start >= 30:
                break
            directory_path = Path(str(directory[0]))
            conn.execute(
                "DELETE FROM refresh_directories WHERE path = ?", (str(directory_path),)
            )
            try:
                children = list(directory_path.iterdir())
            except (FileNotFoundError, PermissionError, OSError):
                continue
            for child in children:
                try:
                    if child.is_dir():
                        conn.execute(
                            "INSERT OR IGNORE INTO refresh_directories(path) VALUES (?)",
                            (normalize_path(child),),
                        )
                    elif child.is_file() and child.suffix.lower() in SUPPORTED_EXTS:
                        cursor = conn.execute(
                            "INSERT OR IGNORE INTO refresh_paths(path) VALUES (?)",
                            (normalize_path(child),),
                        )
                        discovered += cursor.rowcount
                except OSError:
                    continue

        rows = conn.execute(
            "SELECT path FROM refresh_paths ORDER BY path LIMIT ?",
            (_REFRESH_PATH_BATCH_SIZE,),
        ).fetchall()
        paths = [str(row[0]) for row in rows]
        if paths:
            conn.executemany(
                "DELETE FROM refresh_paths WHERE path = ?", [(path,) for path in paths]
            )
        # Discovery count records every path that becomes ready for indexing once.
        return paths, discovered

    def _read_keyword_states_with_retries(
        self, exif: ExifTool, paths: list[str]
    ) -> dict[str, KeywordState]:
        """Read one batch, degrading extant unreadable files after retries."""
        for attempt in range(3):
            try:
                return exif.read_keywords_many(paths)
            except Exception:
                if attempt == 2:
                    return {}
                time.sleep(0.1 * (attempt + 1))
        raise AssertionError("retry loop must return")

    @staticmethod
    def _unreadable_state(path: str) -> KeywordState | None:
        try:
            if Path(path).exists():
                return KeywordState([], [], iptc_readable=False, xmp_readable=False)
        except OSError:
            pass
        return None

    def _index_refresh_paths(
        self, conn: sqlite3.Connection, exif: ExifTool, paths: list[str]
    ) -> tuple[int, int, int]:
        states: dict[str, KeywordState] = {}
        started = time.monotonic()
        processed: list[str] = []
        for offset in range(0, len(paths), _REFRESH_EXIF_SUBGROUP_SIZE):
            subgroup = paths[offset : offset + _REFRESH_EXIF_SUBGROUP_SIZE]
            states.update(self._read_keyword_states_with_retries(exif, subgroup))
            processed.extend(subgroup)
            # The time boundary is intentionally checked only between ExifTool
            # subgroups; no subprocess is interrupted mid-request.
            if time.monotonic() - started >= 30:
                break

        for path in paths[len(processed) :]:
            conn.execute(
                "INSERT OR IGNORE INTO refresh_paths(path) VALUES (?)", (path,)
            )

        updated = 0
        deleted = 0
        for path in processed:
            state = states.get(path) or self._unreadable_state(path)
            if state is None:
                conn.execute("DELETE FROM photos WHERE path = ?", (path,))
                deleted += 1
                continue
            try:
                self.upsert_state(conn, path, state)
            except FileNotFoundError:
                conn.execute("DELETE FROM photos WHERE path = ?", (path,))
                deleted += 1
            else:
                updated += 1
        self._prune_orphan_tags(conn)
        return updated, deleted, len(processed)

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
        force_migration: bool = True,
    ) -> IndexSyncResult:
        current_paths = [
            normalize_path(path)
            for path in paths
            if Path(path).suffix.lower() in SUPPORTED_EXTS
        ]
        current_set = set(current_paths)
        updated_count = 0

        with self._connection() as conn:
            migration_pending = self._keyword_index_rebuild_pending(conn)
            effective_force = force or (
                force_migration and migration_pending and deletion_directory is None
            )
            existing = self._photo_rows(conn, current_paths)
            changed: list[str] = []
            for photo_path in current_paths:
                try:
                    stat = Path(photo_path).stat()
                except FileNotFoundError:
                    continue
                row = existing.get(photo_path)
                if (
                    effective_force
                    or row is None
                    or int(row["mtime"]) != int(stat.st_mtime)
                    or int(row["size"]) != int(stat.st_size)
                ):
                    changed.append(photo_path)

            if changed:
                states = self._read_keyword_states_with_retries(exif, changed)
                for photo_path in changed:
                    state = states.get(photo_path) or self._unreadable_state(photo_path)
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
                if migration_pending:
                    conn.execute(
                        "INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)",
                        (_KEYWORD_INDEX_VERSION_META_KEY, _KEYWORD_INDEX_VERSION),
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
