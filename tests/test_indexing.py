import tempfile
import unittest
from pathlib import Path

from exif_tool import KeywordState
from indexing import _PATH_QUERY_BATCH_SIZE, PhotoIndex
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


if __name__ == "__main__":
    unittest.main()
