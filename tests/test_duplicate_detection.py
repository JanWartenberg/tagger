import tempfile
import unittest
from pathlib import Path

from exif_tool import KeywordState
from services.duplicate_detection import (
    ExifToolCaptureMetadataReader,
    IndexedPhotoScope,
    MetadataReadError,
    PhotoMetadata,
    SameCaptureTimestampDetector,
    ScanRequest,
    SubfolderPhotoScope,
)
from services.photo_discovery import FileSystemPhotoDiscovery
from utils import normalize_path


class MappingReader:
    def __init__(self, records):
        self.records = {
            normalize_path(path): record for path, record in records.items()
        }
        self.batches = []

    def read_many(self, paths):
        self.batches.append(tuple(paths))
        return {path: self.records.get(path) for path in paths}


class DuplicateDetectionTests(unittest.TestCase):
    def test_groups_original_dates_and_create_fallback(self):
        paths = ("z.jpg", "a.jpg", "fallback.jpg", "other.jpg")
        reader = MappingReader(
            {
                "z.jpg": PhotoMetadata(" 2024:01:02 03:04:05 ", "other"),
                "a.jpg": PhotoMetadata("2024:01:02 03:04:05", None),
                "fallback.jpg": PhotoMetadata(None, "2024:01:02 03:04:05"),
                "other.jpg": PhotoMetadata("different", None),
            }
        )
        result = SameCaptureTimestampDetector().scan(ScanRequest("scan", paths), reader)

        self.assertTrue(result.complete)
        self.assertEqual(len(result.groups), 1)
        members = result.groups[0].members
        self.assertEqual(
            [member.path for member in members],
            [normalize_path(path) for path in ("a.jpg", "fallback.jpg", "z.jpg")],
        )
        self.assertEqual(members[1].source_field, "EXIF:CreateDate")
        self.assertEqual(members[0].timestamp, "2024:01:02 03:04:05")

    def test_omits_timestamp_less_photos_and_keeps_bursts(self):
        reader = MappingReader(
            {
                "a.jpg": PhotoMetadata(None, None),
                "b.jpg": PhotoMetadata("same", None),
                "c.jpg": PhotoMetadata("same", None),
                "d.jpg": PhotoMetadata("same", None),
            }
        )
        result = SameCaptureTimestampDetector().scan(
            ScanRequest("scan", ("d.jpg", "b.jpg", "a.jpg", "c.jpg")), reader
        )

        self.assertEqual(
            [m.path for m in result.groups[0].members],
            [normalize_path(path) for path in ("b.jpg", "c.jpg", "d.jpg")],
        )
        self.assertEqual(result.timestampless_paths, (normalize_path("a.jpg"),))

    def test_partial_read_failure_is_reported_without_losing_groups(self):
        reader = MappingReader(
            {
                "a.jpg": PhotoMetadata("same", None),
                "b.jpg": PhotoMetadata("same", None),
                "bad.jpg": MetadataReadError("unreadable"),
            }
        )
        result = SameCaptureTimestampDetector().scan(
            ScanRequest("scan", ("bad.jpg", "b.jpg", "a.jpg")), reader
        )

        self.assertEqual(len(result.groups), 1)
        self.assertEqual(result.errors[0].path, normalize_path("bad.jpg"))

    def test_batches_progress_and_cancellation_do_not_complete(self):
        reader = MappingReader({path: PhotoMetadata("same", None) for path in "abcd"})
        progress = []
        result = SameCaptureTimestampDetector().scan(
            ScanRequest("scan", tuple(f"{path}.jpg" for path in "abcd")),
            reader,
            batch_size=2,
            on_progress=progress.append,
            is_cancelled=lambda: len(reader.batches) >= 1,
        )

        self.assertFalse(result.complete)
        self.assertEqual(result.processed, 2)
        self.assertEqual([(item.processed, item.total) for item in progress], [(2, 4)])

    def test_request_freezes_normalized_deduplicated_paths(self):
        request = ScanRequest("scan", ("b.jpg", "a.jpg", "b.jpg"))
        self.assertEqual(
            request.paths,
            (normalize_path("a.jpg"), normalize_path("b.jpg")),
        )


class ScopeAdapterTests(unittest.TestCase):
    def test_index_scope_snapshots_paths_through_public_operation(self):
        class FakeIndex:
            def snapshot_photo_paths(self):
                return ["z.jpg", "a.jpg"]

        request = IndexedPhotoScope(FakeIndex()).snapshot("scan")
        self.assertEqual(
            request.paths,
            (normalize_path("a.jpg"), normalize_path("z.jpg")),
        )

    def test_subfolder_scope_uses_discovery_and_supported_extensions(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "nested").mkdir()
            (root / "one.JPG").touch()
            (root / "nested" / "two.jpg").touch()
            (root / "ignore.txt").touch()

            request = SubfolderPhotoScope(FileSystemPhotoDiscovery()).snapshot(
                "scan", root
            )

        self.assertEqual(
            request.paths,
            tuple(
                sorted(
                    (
                        normalize_path(root / "one.JPG"),
                        normalize_path(root / "nested" / "two.jpg"),
                    )
                )
            ),
        )


class ExifToolReaderTests(unittest.TestCase):
    def test_missing_record_differs_from_readable_without_date(self):
        class FakeExif:
            def read_keywords_many(self, paths):
                return {paths[0]: KeywordState([], [], None, None)}

        path, missing = "readable.jpg", "missing.jpg"
        records = ExifToolCaptureMetadataReader(FakeExif()).read_many([path, missing])
        self.assertEqual(records[normalize_path(path)], PhotoMetadata())
        self.assertEqual(
            records[normalize_path(missing)],
            MetadataReadError("metadata record unavailable"),
        )


if __name__ == "__main__":
    unittest.main()
