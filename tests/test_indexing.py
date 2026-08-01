import sqlite3
import tempfile
from contextlib import closing
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from exif_tool import KeywordState
from indexing import DateQueryError, _PATH_QUERY_BATCH_SIZE, PhotoIndex
from utils import normalize_path


class FakeExifTool:
    def __init__(self) -> None:
        self.read_batches: list[list[str]] = []

    def read_keywords_many(self, paths: list[str]) -> dict[str, KeywordState]:
        self.read_batches.append(paths)
        return {path: KeywordState(["indexed"], ["indexed"]) for path in paths}


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
