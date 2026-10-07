from tagger_app.services.duplicate_detection import CandidateGroup, CandidateMember
from tagger_app.services.ignored_candidates import IgnoredCandidateStore


def candidate(
    root,
    *,
    timestamp="2024:01:02 03:04:05",
    field="EXIF:DateTimeOriginal",
    tags=(),
    extra=False,
):
    members = [
        CandidateMember(str(root / name), timestamp, field, tags)
        for name in ("a.jpg", "b.jpg")
    ]
    if extra:
        members.append(CandidateMember(str(root / "c.jpg"), timestamp, field))
    return CandidateGroup("scan-local-id", tuple(members))


def test_ignore_survives_reopening_store_and_is_isolated_per_index(tmp_path):
    root = tmp_path / "photos"
    group = candidate(root)
    store = IgnoredCandidateStore(root)
    store.remember("same-capture-timestamp", group)

    reopened = IgnoredCandidateStore(root)
    assert reopened.is_ignored("same-capture-timestamp", group)
    assert reopened.list()[0].group == group
    assert not IgnoredCandidateStore(tmp_path / "other").is_ignored(
        "same-capture-timestamp", group
    )


def test_restore_and_clear_are_explicit_and_inspection_preserves_ignores(tmp_path):
    store = IgnoredCandidateStore(tmp_path)
    first = candidate(tmp_path)
    second = candidate(tmp_path, timestamp="2025:01:02 03:04:05")
    store.remember("same-capture-timestamp", first)
    store.remember("same-capture-timestamp", second)
    records = store.list()
    assert len(store.list()) == 2
    store.restore(records[0].identity)
    assert store.is_ignored("same-capture-timestamp", first)
    assert not store.is_ignored("same-capture-timestamp", second)
    store.clear()
    assert store.list() == ()


def test_identity_tracks_detector_members_and_capture_evidence_but_not_tags(tmp_path):
    from dataclasses import replace

    store = IgnoredCandidateStore(tmp_path)
    group = candidate(tmp_path)
    store.remember("same-capture-timestamp", group)
    same = replace(candidate(tmp_path, tags=("new tag",)), group_id="new-scan-id")
    same = replace(same, members=tuple(reversed(same.members)))
    assert store.is_ignored("same-capture-timestamp", same)
    assert not store.is_ignored("other-detector", group)
    assert not store.is_ignored(
        "same-capture-timestamp", candidate(tmp_path, extra=True)
    )
    assert not store.is_ignored(
        "same-capture-timestamp", candidate(tmp_path, timestamp="2025:01:02 03:04:05")
    )
    assert not store.is_ignored(
        "same-capture-timestamp", candidate(tmp_path, field="EXIF:CreateDate")
    )
    assert not store.is_ignored(
        "same-capture-timestamp", candidate(tmp_path / "renamed")
    )


def test_listing_unused_index_does_not_create_storage(tmp_path):
    assert IgnoredCandidateStore(tmp_path).list() == ()
    assert not (tmp_path / ".tagger").exists()


def test_scan_loads_ignored_identities_in_its_worker(tmp_path):
    from tagger_app.services.duplicate_detection import (
        DuplicateScanCompleted,
        DuplicateScanCoordinator,
        DuplicateScopeKind,
        DuplicateScopeSnapshot,
        PhotoMetadata,
        SameCaptureTimestampDetector,
    )

    group = candidate(tmp_path)
    store = IgnoredCandidateStore(tmp_path)
    store.remember("same-capture-timestamp", group)
    queued = []
    events = []

    class Runner:
        def submit(self, work):
            queued.append(work)

    class Reader:
        def read_many(self, paths):
            return {path: PhotoMetadata("2024:01:02 03:04:05") for path in paths}

    coordinator = DuplicateScanCoordinator(
        reader=Reader(), runner=Runner(), event_sink=events.append
    )
    snapshot = DuplicateScopeSnapshot(
        "scope",
        DuplicateScopeKind.INDEX_DATABASE,
        str(tmp_path),
        tuple(m.path for m in group.members),
    )
    loads = []

    def load():
        loads.append(True)
        return frozenset(record.identity for record in store.list())

    coordinator.start(snapshot, SameCaptureTimestampDetector(), load_ignored=load)
    assert loads == []
    queued.pop()()
    assert isinstance(events[-1], DuplicateScanCompleted)
    assert len(events[-1].ignored_identities) == 1


def test_candidate_identity_uses_scan_paths_without_filesystem_access(
    tmp_path, monkeypatch
):
    from pathlib import Path
    from tagger_app.services.ignored_candidates import candidate_identity

    group = candidate(tmp_path)

    def inaccessible_filesystem(*args, **kwargs):
        raise AssertionError("Identity must not access the filesystem")

    monkeypatch.setattr(Path, "resolve", inaccessible_filesystem)
    identity = candidate_identity("same-capture-timestamp", group)
    assert len(identity) == 64
    assert identity != candidate_identity("other-detector", group)
