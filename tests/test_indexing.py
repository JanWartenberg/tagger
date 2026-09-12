import sqlite3
import tempfile
from contextlib import closing
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from exif_tool import KeywordState
from indexing import (
    DateQueryError,
    IndexRefreshProgress,
    IndexSyncResult,
    _PATH_QUERY_BATCH_SIZE,
    PhotoIndex,
)
from utils import normalize_path


class FakeExifTool:
    def __init__(self) -> None:
        self.read_batches: list[list[str]] = []

    def read_keywords_many(self, paths: list[str]) -> dict[str, KeywordState]:
        self.read_batches.append(paths)
        return {path: KeywordState(["indexed"], ["indexed"]) for path in paths}


class PhotoIndexCanonicalKeywordFactTests(unittest.TestCase):
    def test_index_projects_only_normalized_iptc_keywords(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            photo = root / "photo.jpg"
            photo.touch()
            path = normalize_path(photo)
            index = PhotoIndex(root)

            index.update_states(
                {
                    path: KeywordState(
                        ["  cafe\u0301 ", "Café", "IPTC only"],
                        ["XMP only", "Café"],
                    )
                }
            )

            self.assertEqual(index.load_tags_for_photo(path), ["café", "IPTC only"])
            self.assertEqual(index.load_known_tags(), {"café", "IPTC only"})
            self.assertEqual(index.search_photos("tag:XMP only"), [])
            self.assertEqual(index.search_photos("tag:café"), [path])

    def test_sync_normalizes_unicode_and_redundant_absolute_path_segments(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            photo_dir = root / "Fotos ü"
            photo_dir.mkdir()
            photo = photo_dir / "bild-é.jpg"
            photo.touch()
            raw_path = root / "Fotos ü" / ".." / "Fotos ü" / "bild-é.jpg"
            normalized = normalize_path(photo)
            index = PhotoIndex(root)

            result = index.sync_paths(FakeExifTool(), [str(raw_path)], force=True)

            self.assertEqual(result.scanned_count, 1)
            self.assertEqual(index.has_photos([str(raw_path)]), {normalized})
            self.assertEqual(index.search_photos("tag:indexed"), [normalized])

    def test_iptc_empty_query_is_scoped_to_workspace_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            included = root / "workspace-empty.jpg"
            excluded = root / "outside-workspace-empty.jpg"
            tagged = root / "workspace-tagged.jpg"
            for photo in (included, excluded, tagged):
                photo.touch()
            index = PhotoIndex(root)
            index.update_states(
                {
                    normalize_path(included): KeywordState([], []),
                    normalize_path(excluded): KeywordState([], []),
                    normalize_path(tagged): KeywordState(["bird"], ["bird"]),
                }
            )

            result = index.load_iptc_empty_photos(
                [normalize_path(included), normalize_path(tagged)]
            )

            self.assertEqual(result.paths, (normalize_path(included),))

    def test_iptc_empty_query_includes_unreadable_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = {
                name: normalize_path(root / name)
                for name in ("empty.jpg", "unknown.jpg", "tagged.jpg")
            }
            for path in paths.values():
                Path(path).touch()
            index = PhotoIndex(root)
            index.update_states(
                {
                    paths["empty.jpg"]: KeywordState([], []),
                    paths["unknown.jpg"]: KeywordState(
                        [], [], iptc_readable=False, xmp_readable=False
                    ),
                    paths["tagged.jpg"]: KeywordState(["bird"], ["bird"]),
                }
            )

            result = index.load_iptc_empty_photos(list(paths.values()))

            self.assertEqual(result.paths, (paths["empty.jpg"], paths["unknown.jpg"]))
            self.assertEqual(result.unknown_paths, {paths["unknown.jpg"]})

    def test_legacy_merged_facts_are_cleared_then_rebuilt_from_iptc(self) -> None:
        class CanonicalExifTool:
            def __init__(self) -> None:
                self.read_batches: list[list[str]] = []

            def read_keywords_many(self, paths: list[str]) -> dict[str, KeywordState]:
                self.read_batches.append(paths)
                return {
                    path: KeywordState(["IPTC fact"], ["legacy XMP fact"])
                    for path in paths
                }

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            photo = root / "photo.jpg"
            photo.touch()
            path = normalize_path(photo)
            seeded = PhotoIndex(root)
            seeded.update_states({path: KeywordState(["old"], ["old"])})
            with seeded._connection() as conn:
                conn.execute("DELETE FROM photo_tags")
                conn.execute("DELETE FROM tags")
                conn.execute("INSERT INTO tags(tag) VALUES (?)", ("legacy XMP fact",))
                tag_id = conn.execute(
                    "SELECT id FROM tags WHERE tag = ?", ("legacy XMP fact",)
                ).fetchone()[0]
                conn.execute(
                    "INSERT INTO photo_tags(photo_path, tag_id) VALUES (?, ?)",
                    (path, tag_id),
                )
                conn.execute(
                    "DELETE FROM meta WHERE key = ?", ("keyword_index_version",)
                )
                conn.execute(
                    "INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)",
                    ("initialized", "1"),
                )

            index = PhotoIndex(root)

            self.assertTrue(index.needs_keyword_index_rebuild())
            self.assertFalse(index.is_initialized())
            self.assertEqual(index.search_photos("tag:legacy XMP fact"), [])

            exif = CanonicalExifTool()
            index.sync_paths(exif, [path])

            self.assertEqual(exif.read_batches, [[path]])
            self.assertFalse(index.needs_keyword_index_rebuild())
            self.assertTrue(index.is_initialized())
            self.assertEqual(index.search_photos("tag:legacy XMP fact"), [])
            self.assertEqual(index.search_photos("tag:IPTC fact"), [path])


class PhotoIndexConnectionLifecycleTests(unittest.TestCase):
    def test_connection_context_commits_and_closes_on_success(self) -> None:
        index = PhotoIndex("/photos")
        connection = Mock()

        with patch.object(index, "_connect", return_value=connection):
            with index._connection() as active_connection:
                self.assertIs(active_connection, connection)

        connection.commit.assert_called_once_with()
        connection.rollback.assert_not_called()
        connection.close.assert_called_once_with()

    def test_connection_context_rolls_back_and_closes_on_failure(self) -> None:
        index = PhotoIndex("/photos")
        connection = Mock()

        with patch.object(index, "_connect", return_value=connection):
            with self.assertRaisesRegex(RuntimeError, "write failed"):
                with index._connection():
                    raise RuntimeError("write failed")

        connection.commit.assert_not_called()
        connection.rollback.assert_called_once_with()
        connection.close.assert_called_once_with()


class PhotoIndexPathBatchingTests(unittest.TestCase):
    def test_large_workspace_iptc_empty_query_is_batched(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = []
            for number in range(_PATH_QUERY_BATCH_SIZE + 2):
                path = root / f"photo-{number:04}.jpg"
                path.touch()
                paths.append(normalize_path(path))
            index = PhotoIndex(root)
            index.update_states({path: KeywordState([], []) for path in paths})

            result = index.load_iptc_empty_photos(paths)

            self.assertEqual(result.paths, tuple(paths))

    def test_large_path_sets_preserve_membership_and_sync_lookup_results(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = []
            for number in range(_PATH_QUERY_BATCH_SIZE + 2):
                path = root / f"photo-{number:04}.jpg"
                path.touch()
                paths.append(normalize_path(path))

            index = PhotoIndex(root)
            known_paths = paths[::2]
            state = KeywordState(["known"], ["known"])
            index.update_states({path: state for path in known_paths})

            self.assertEqual(index.has_photos(paths), set(known_paths))

            exif = FakeExifTool()
            first_sync = index.sync_root(exif)
            self.assertEqual(first_sync.updated_count, len(paths))
            self.assertEqual(
                {path for batch in exif.read_batches for path in batch}, set(paths)
            )

            exif.read_batches.clear()
            second_sync = index.sync_root(exif)
            self.assertEqual(second_sync.updated_count, len(paths))
            self.assertEqual(
                {path for batch in exif.read_batches for path in batch}, set(paths)
            )

    def test_refresh_timestamp_marks_staleness_and_full_sync_removes_deleted_photos(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            kept = root / "kept.jpg"
            deleted = root / "deleted.jpg"
            discovered = root / "discovered.jpg"
            kept.touch()
            deleted.touch()
            index = PhotoIndex(root)
            exif = FakeExifTool()

            index.sync_root(exif)
            last_refresh = index.last_index_refresh()

            self.assertIsNotNone(last_refresh)
            self.assertFalse(
                index.is_refresh_stale(now=last_refresh + 24 * 60 * 60 - 1)
            )
            self.assertTrue(index.is_refresh_stale(now=last_refresh + 24 * 60 * 60))

            deleted.unlink()
            discovered.touch()
            refreshed = index.sync_root(exif)

            self.assertEqual(refreshed.deleted_count, 1)
            self.assertEqual(
                index.has_photos([str(kept), str(deleted), str(discovered)]),
                {str(kept), str(discovered)},
            )
            self.assertEqual(
                index.search_photos("tag:indexed"),
                [normalize_path(discovered), normalize_path(kept)],
            )

    def test_local_repair_evicts_one_path_and_reconciles_only_its_parent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            parent = root / "parent"
            nested = parent / "nested"
            other = root / "other"
            parent.mkdir()
            nested.mkdir()
            other.mkdir()
            missing = parent / "missing.jpg"
            discovered = parent / "discovered.jpg"
            nested_photo = nested / "nested.jpg"
            other_photo = other / "other.jpg"
            for path in (missing, nested_photo, other_photo):
                path.touch()

            index = PhotoIndex(root)
            exif = FakeExifTool()
            index.sync_root(exif)
            missing.unlink()
            discovered.touch()

            self.assertTrue(index.remove_photo(str(missing)))
            repaired = index.sync_directory(exif, parent)

            self.assertEqual(repaired.scanned_count, 1)
            self.assertEqual(repaired.deleted_count, 0)
            self.assertEqual(
                index.has_photos(
                    [str(missing), str(discovered), str(nested_photo), str(other_photo)]
                ),
                {str(discovered), str(nested_photo), str(other_photo)},
            )
            self.assertEqual(index.load_known_tags(), {"indexed"})


class PhotoIndexResumableRefreshTests(unittest.TestCase):
    def test_refresh_streams_bounded_chunks_then_reconciles_and_cleans_checkpoint(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for number in range(1_001):
                (root / f"photo-{number:04}.jpg").touch()
            index = PhotoIndex(root)
            exif = FakeExifTool()

            first = index.refresh_step(exif)
            self.assertIsInstance(first, IndexRefreshProgress)
            self.assertEqual(first.phase, "discovering")
            self.assertEqual(first.indexed_count, 1_000)
            self.assertEqual(sum(map(len, exif.read_batches)), 1_000)

            resumed = PhotoIndex(root).refresh_step(exif)
            self.assertIsInstance(resumed, IndexRefreshProgress)
            self.assertTrue(resumed.resumed)
            self.assertEqual(resumed.indexed_count, 1_001)

            self.assertIsInstance(index.refresh_step(exif), IndexRefreshProgress)
            completed = index.refresh_step(exif)
            self.assertIsInstance(completed, IndexSyncResult)
            self.assertEqual(completed.updated_count, 1_001)
            self.assertFalse(index.is_refresh_stale())
            self.assertFalse(index.cancel_refresh())

    def test_third_subgroup_failure_keeps_existing_photo_as_unknown(self) -> None:
        class FailingExifTool:
            calls = 0

            def read_keywords_many(self, _paths: list[str]) -> dict[str, KeywordState]:
                self.calls += 1
                raise RuntimeError("ExifTool failed")

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            photo = root / "photo.jpg"
            photo.touch()
            index = PhotoIndex(root)
            exif = FailingExifTool()

            self.assertIsInstance(index.refresh_step(exif), IndexRefreshProgress)

            self.assertEqual(exif.calls, 3)
            self.assertEqual(
                index.load_iptc_empty_photos([normalize_path(photo)]).unknown_paths,
                {normalize_path(photo)},
            )

    def test_cancel_discards_durable_recovery_state(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "photo.jpg").touch()
            index = PhotoIndex(root)

            self.assertIsInstance(
                index.refresh_step(FakeExifTool()), IndexRefreshProgress
            )
            self.assertTrue(index.cancel_refresh())
            self.assertFalse(index.cancel_refresh())


class CaptureDateExifTool:
    def read_keywords_many(self, paths: list[str]) -> dict[str, KeywordState]:
        return {
            path: KeywordState([], [], date_original="2025:04:21 17:41:35")
            for path in paths
        }


class PhotoIndexDateSearchTests(unittest.TestCase):
    def test_date_queries_use_normalized_calendar_dates_and_unknown_values(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = {
                name: normalize_path(root / name)
                for name in ("january.jpg", "february.jpg", "march.jpg", "unknown.jpg")
            }
            for path in paths.values():
                Path(path).touch()

            index = PhotoIndex(root)
            index.update_states(
                {
                    paths["january.jpg"]: KeywordState(
                        [], [], date_original="2024:01:31 23:30:00+01:00"
                    ),
                    paths["february.jpg"]: KeywordState(
                        [], [], date_create="2024:02:01 00:30:00"
                    ),
                    paths["march.jpg"]: KeywordState(
                        [],
                        [],
                        date_original="not a date",
                        date_create="2024:03:01 12:00:00",
                    ),
                    paths["unknown.jpg"]: KeywordState(
                        [], [], date_xmp_create="2024:04:01T12:00:00"
                    ),
                }
            )

            self.assertEqual(
                index.search_photos("date:2024"),
                [paths["february.jpg"], paths["january.jpg"]],
            )
            self.assertEqual(
                index.search_photos("date:2024-01"), [paths["january.jpg"]]
            )
            self.assertEqual(
                index.search_photos("date:2024-01-31"), [paths["january.jpg"]]
            )
            self.assertEqual(
                index.search_photos("date:2024-01-31..2024-02-01"),
                [paths["february.jpg"], paths["january.jpg"]],
            )
            self.assertEqual(
                index.search_photos("date:unknown"),
                [paths["march.jpg"], paths["unknown.jpg"]],
            )

    def test_tag_and_date_terms_intersect_in_one_indexed_search(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = {
                name: normalize_path(root / name)
                for name in (
                    "beach-january.jpg",
                    "beach-february.jpg",
                    "city-january.jpg",
                )
            }
            for path in paths.values():
                Path(path).touch()
            index = PhotoIndex(root)
            index.update_states(
                {
                    paths["beach-january.jpg"]: KeywordState(
                        ["beach"], ["beach"], date_original="2024:01:15 12:00:00"
                    ),
                    paths["beach-february.jpg"]: KeywordState(
                        ["beach"], ["beach"], date_original="2024:02:15 12:00:00"
                    ),
                    paths["city-january.jpg"]: KeywordState(
                        ["city"], ["city"], date_original="2024:01:15 12:00:00"
                    ),
                }
            )

            self.assertEqual(
                index.search_photos("tag:beach date:2024-01"),
                [paths["beach-january.jpg"]],
            )
            with self.assertRaises(DateQueryError):
                index.search_photos("tag:beach date:2024-02-30")

    def test_date_index_migration_backfills_existing_raw_values(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            db_path = root / ".tagger" / "index.sqlite"
            db_path.parent.mkdir()
            with closing(sqlite3.connect(db_path)) as conn:
                with conn:
                    conn.execute(
                        """
                        CREATE TABLE photos(
                          path TEXT PRIMARY KEY,
                          mtime INTEGER NOT NULL,
                          size INTEGER NOT NULL,
                          date_taken TEXT
                        )
                        """
                    )
                    conn.executemany(
                        "INSERT INTO photos(path, mtime, size, date_taken) VALUES (?, 0, 0, ?)",
                        [
                            ("/photos/valid.jpg", "2024:02:29 12:00:00"),
                            ("/photos/unusable.jpg", "2024:02:30 12:00:00"),
                        ],
                    )

            index = PhotoIndex(root)

            self.assertEqual(
                index.search_photos("date:2024-02-29"), ["/photos/valid.jpg"]
            )
            self.assertEqual(
                index.search_photos("date:unknown"), ["/photos/unusable.jpg"]
            )

    def test_full_sync_reindexes_unchanged_legacy_photo_dates(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            photo = root / "photo.jpg"
            photo.touch()
            path = normalize_path(photo)
            stat = photo.stat()
            db_path = root / ".tagger" / "index.sqlite"
            db_path.parent.mkdir()
            with closing(sqlite3.connect(db_path)) as conn:
                with conn:
                    conn.execute(
                        """
                        CREATE TABLE photos(
                          path TEXT PRIMARY KEY,
                          mtime INTEGER NOT NULL,
                          size INTEGER NOT NULL,
                          date_taken TEXT
                        )
                        """
                    )
                    conn.execute(
                        "INSERT INTO photos(path, mtime, size, date_taken) VALUES (?, ?, ?, '')",
                        (path, int(stat.st_mtime), int(stat.st_size)),
                    )

            index = PhotoIndex(root)

            refreshed = index.sync_root(CaptureDateExifTool())

            self.assertEqual(refreshed.updated_count, 1)
            self.assertEqual(index.search_photos("date:2025"), [path])

    def test_invalid_date_queries_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            index = PhotoIndex(directory)

            for query in (
                "date:",
                "date:2024-13",
                "date:2024-02-30",
                "date:2024..2025",
                "date:2024-01-01..2024-01",
                "date:tomorrow",
            ):
                with self.subTest(query=query):
                    with self.assertRaises(DateQueryError):
                        index.search_photos(query)


if __name__ == "__main__":
    unittest.main()
