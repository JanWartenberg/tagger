import sqlite3
import tempfile
import unittest
from pathlib import Path

from exif_tool import KeywordState
from indexing import DateQueryError, _PATH_QUERY_BATCH_SIZE, PhotoIndex
from utils import normalize_path


class FakeExifTool:
    def __init__(self) -> None:
        self.read_batches: list[list[str]] = []

    def read_keywords_many(self, paths: list[str]) -> dict[str, KeywordState]:
        self.read_batches.append(paths)
        return {path: KeywordState(["indexed"], ["indexed"]) for path in paths}


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
            self.assertEqual(first_sync.updated_count, len(paths) - len(known_paths))
            self.assertEqual(
                {path for batch in exif.read_batches for path in batch},
                set(paths) - set(known_paths),
            )

            exif.read_batches.clear()
            second_sync = index.sync_root(exif)
            self.assertEqual(second_sync.updated_count, 0)
            self.assertEqual(exif.read_batches, [])

    def test_refresh_timestamp_marks_staleness_and_full_sync_removes_deleted_photos(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            kept = root / "kept.jpg"
            deleted = root / "deleted.jpg"
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
            refreshed = index.sync_root(exif)

            self.assertEqual(refreshed.deleted_count, 1)
            self.assertEqual(index.has_photos([str(kept), str(deleted)]), {str(kept)})


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
            with sqlite3.connect(db_path) as conn:
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
