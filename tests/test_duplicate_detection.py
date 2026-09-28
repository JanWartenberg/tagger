import tempfile
import unittest
from pathlib import Path

from tagger_app.exif_tool import KeywordState
from tagger_app.services.duplicate_detection import (
    DuplicateScanCompleted,
    DuplicateScanCoordinator,
    DuplicateScanProgress,
    DuplicateScopeCoordinator,
    DuplicateScopeKind,
    ExifToolCaptureMetadataReader,
    IndexedPhotoScope,
    MetadataReadError,
    PhotoMetadata,
    SameCaptureTimestampDetector,
    ScanRequest,
    ScopePreparationCompleted,
    ScopePreparationFailed,
    SubfolderPhotoScope,
)
from tagger_app.services.photo_discovery import FileSystemPhotoDiscovery
from tagger_app.utils import normalize_path


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

    def test_all_zero_original_date_uses_create_fallback_or_is_omitted(self):
        fallback = "2024:01:02 03:04:05"
        reader = MappingReader(
            {
                "fallback.jpg": PhotoMetadata("0000:00:00 00:00:00", fallback),
                "peer.jpg": PhotoMetadata(fallback, None),
                "zero.jpg": PhotoMetadata("000000", " 0000:00:00 00:00:00 "),
            }
        )

        result = SameCaptureTimestampDetector().scan(
            ScanRequest("scan", ("fallback.jpg", "peer.jpg", "zero.jpg")), reader
        )

        self.assertEqual(len(result.groups), 1)
        self.assertEqual(result.groups[0].members[0].source_field, "EXIF:CreateDate")
        self.assertEqual(result.timestampless_paths, (normalize_path("zero.jpg"),))

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


class ScopeCoordinatorTests(unittest.TestCase):
    class Runner:
        def __init__(self):
            self.work = []

        def submit(self, work):
            self.work.append(work)

        def run(self, index=0):
            self.work.pop(index)()

    class Discovery:
        def __init__(self, results):
            self.results = results

        def discover(self, root):
            result = self.results[root]
            if isinstance(result, Exception):
                raise result
            return result

    class Index:
        def __init__(self, paths):
            self.paths = paths

        def snapshot_photo_paths(self):
            return self.paths

    def test_prepares_immutable_index_and_subfolder_snapshots(self):
        runner = self.Runner()
        events = []
        discovery = self.Discovery(
            {normalize_path("folder"): ["folder/b.jpg", "folder/a.jpg"]}
        )
        coordinator = DuplicateScopeCoordinator(
            discovery=discovery,
            index_factory=lambda _root: self.Index(["index/b.jpg", "index/a.jpg"]),
            runner=runner,
            event_sink=events.append,
        )

        coordinator.prepare_index("index-root")
        runner.run()
        coordinator.prepare_subfolder("folder")
        runner.run()

        self.assertEqual(len(events), 2)
        self.assertTrue(
            all(isinstance(event, ScopePreparationCompleted) for event in events)
        )
        self.assertEqual(events[0].snapshot.kind, DuplicateScopeKind.INDEX_DATABASE)
        self.assertEqual(
            events[0].snapshot.paths,
            (normalize_path("index/a.jpg"), normalize_path("index/b.jpg")),
        )
        self.assertEqual(events[1].snapshot.kind, DuplicateScopeKind.SUBFOLDER)
        self.assertEqual(events[1].snapshot.root, normalize_path("folder"))

    def test_freezes_paths_from_completed_shared_folder_discovery(self):
        runner = self.Runner()
        events = []
        discovery = self.Discovery({})
        coordinator = DuplicateScopeCoordinator(
            discovery=discovery,
            index_factory=lambda _root: self.Index([]),
            runner=runner,
            event_sink=events.append,
        )

        coordinator.prepare_discovered_subfolder(
            "folder", ("folder/b.jpg", "folder/a.jpg")
        )
        runner.run()

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].snapshot.kind, DuplicateScopeKind.SUBFOLDER)
        self.assertEqual(events[0].snapshot.root, normalize_path("folder"))
        self.assertEqual(
            events[0].snapshot.paths,
            (normalize_path("folder/a.jpg"), normalize_path("folder/b.jpg")),
        )

    def test_superseded_scope_cannot_publish_after_newer_scope(self):
        runner = self.Runner()
        events = []
        discovery = self.Discovery(
            {
                normalize_path("old"): ["old/photo.jpg"],
                normalize_path("new"): ["new/photo.jpg"],
            }
        )
        coordinator = DuplicateScopeCoordinator(
            discovery=discovery,
            index_factory=lambda _root: self.Index([]),
            runner=runner,
            event_sink=events.append,
        )

        coordinator.prepare_subfolder("old")
        coordinator.prepare_subfolder("new")
        runner.run(1)
        runner.run(0)

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].snapshot.root, normalize_path("new"))

    def test_current_scope_failure_is_reported(self):
        runner = self.Runner()
        events = []
        discovery = self.Discovery(
            {normalize_path("broken"): RuntimeError("cannot enumerate")}
        )
        coordinator = DuplicateScopeCoordinator(
            discovery=discovery,
            index_factory=lambda _root: self.Index([]),
            runner=runner,
            event_sink=events.append,
        )

        coordinator.prepare_subfolder("broken")
        runner.run()

        self.assertEqual(len(events), 1)
        self.assertIsInstance(events[0], ScopePreparationFailed)
        self.assertEqual(events[0].error, "cannot enumerate")


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

    def test_preserves_canonical_tags_and_readability_for_review(self):
        class FakeExif:
            def read_keywords_many(self, paths):
                return {
                    paths[0]: KeywordState(
                        ["bird", "archive"],
                        ["ignored-xmp"],
                        "same",
                        None,
                        iptc_readable=False,
                    )
                }

        path = normalize_path("photo.jpg")
        record = ExifToolCaptureMetadataReader(FakeExif()).read_many([path])[path]

        self.assertEqual(record.iptc_tags, ("bird", "archive"))
        self.assertFalse(record.iptc_readable)


class ScanCoordinatorTests(unittest.TestCase):
    class Runner:
        def __init__(self):
            self.work = []

        def submit(self, work):
            self.work.append(work)

        def run(self, index=0):
            self.work.pop(index)()

    def _snapshot(self, scope_id, *paths):
        from tagger_app.services.duplicate_detection import DuplicateScopeSnapshot

        return DuplicateScopeSnapshot(
            scope_id, DuplicateScopeKind.SUBFOLDER, "root", paths
        )

    def test_publishes_progress_and_completed_result(self):
        runner = self.Runner()
        events = []
        reader = MappingReader(
            {
                "a.jpg": PhotoMetadata("same", None, ("source",)),
                "b.jpg": PhotoMetadata("same", None),
            }
        )
        coordinator = DuplicateScanCoordinator(
            reader=reader, runner=runner, event_sink=events.append
        )

        coordinator.start(
            self._snapshot("scope", "a.jpg", "b.jpg"),
            SameCaptureTimestampDetector(),
        )
        runner.run()

        self.assertTrue(
            any(isinstance(event, DuplicateScanProgress) for event in events)
        )
        completed = next(
            event for event in events if isinstance(event, DuplicateScanCompleted)
        )
        self.assertEqual(completed.result.groups[0].members[0].iptc_tags, ("source",))

    def test_cancelled_and_superseded_scans_cannot_publish_results(self):
        runner = self.Runner()
        events = []
        reader = MappingReader(
            {
                "old-a.jpg": PhotoMetadata("old", None),
                "old-b.jpg": PhotoMetadata("old", None),
                "new-a.jpg": PhotoMetadata("new", None),
                "new-b.jpg": PhotoMetadata("new", None),
            }
        )
        coordinator = DuplicateScanCoordinator(
            reader=reader, runner=runner, event_sink=events.append
        )

        coordinator.start(
            self._snapshot("old", "old-a.jpg", "old-b.jpg"),
            SameCaptureTimestampDetector(),
        )
        newest = coordinator.start(
            self._snapshot("new", "new-a.jpg", "new-b.jpg"),
            SameCaptureTimestampDetector(),
        )
        runner.run(0)
        runner.run(0)

        completed = [
            event for event in events if isinstance(event, DuplicateScanCompleted)
        ]
        self.assertEqual(len(completed), 1)
        self.assertEqual(completed[0].request.scan_id, newest.scan_id)


if __name__ == "__main__":
    unittest.main()
