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


if __name__ == "__main__":
    unittest.main()
