"""Folder refresh at the public index and coordinator boundaries."""

from pathlib import Path
from unittest.mock import patch

import pytest

from tagger_app.exif_tool import KeywordState
from tagger_app.indexing import PhotoIndex
from tagger_app.utils import normalize_path


class Metadata:
    def __init__(self):
        self.paths = []
        self.states = {}

    def read_keywords_many(self, paths):
        self.paths.extend(paths)
        return {p: self.states[p] for p in paths if p in self.states}


def test_refresh_folder_recurses_and_reconciles_only_its_subtree(tmp_path):
    folder = tmp_path / "birds"
    nested = folder / "nested"
    nested.mkdir(parents=True)
    sibling = tmp_path / "birds-other"
    sibling.mkdir()
    old, changed, outside = [
        normalize_path(p)
        for p in (folder / "old.jpg", nested / "changed.jpg", sibling / "outside.jpg")
    ]
    for p in (old, changed, outside):
        Path(p).touch()
    index = PhotoIndex(tmp_path)
    initial = Metadata()
    initial.states = {p: KeywordState(["old"], []) for p in (old, changed, outside)}
    index.sync_paths(initial, [old, changed, outside])
    freshness = index.last_index_refresh()
    Path(old).unlink()
    added = normalize_path(folder / "new.JPG")
    Path(added).touch()
    # A nested database marker must never select another database.
    (folder / ".tagger").mkdir()
    metadata = Metadata()
    metadata.states = {
        p: KeywordState(["fresh"], [], date_original="2026:10:18 08:09:00")
        for p in (added, changed)
    }

    paths = index.refresh_folder(metadata, folder)

    assert set(paths) == {added, changed}
    assert set(metadata.paths) == {added, changed}
    assert set(index.search_photos("tag:fresh")) == {added, changed}
    assert index.search_photos("tag:old") == [outside]
    assert set(index.search_photos("date:2026-10")) == {added, changed}
    assert index.last_index_refresh() == freshness


def test_unreadable_metadata_preserves_existing_records_and_reports_failure(tmp_path):
    photo = tmp_path / "photo.jpg"
    photo.touch()
    path = normalize_path(photo)
    index = PhotoIndex(tmp_path)
    index.update_states({path: KeywordState(["keep"], [])})

    with pytest.raises(RuntimeError, match="metadata"):
        index.refresh_folder(Metadata(), tmp_path)

    assert index.search_photos("tag:keep") == [path]


def test_missing_or_incompletely_enumerated_folder_never_removes_records(tmp_path):
    folder = tmp_path / "birds"
    folder.mkdir()
    photo = folder / "photo.jpg"
    photo.touch()
    path = normalize_path(photo)
    index = PhotoIndex(tmp_path)
    index.update_states({path: KeywordState(["keep"], [])})
    photo.unlink()
    folder.rmdir()
    with pytest.raises(OSError):
        index.refresh_folder(Metadata(), folder)
    folder.mkdir()
    with patch("os.scandir", side_effect=PermissionError("unreadable")):
        with pytest.raises(PermissionError):
            index.refresh_folder(Metadata(), folder)
    assert index.search_photos("tag:keep") == [path]


class ManualRunner:
    def __init__(self):
        self.work = []

    def submit(self, work):
        self.work.append(work)

    def drain(self):
        while self.work:
            self.work.pop(0)()


def test_coordinator_deduplicates_refresh_and_serializes_confirmed_writes(tmp_path):
    from tagger_app.services.background_coordinator import (
        BackgroundCoordinator,
        FolderRefreshCompleted,
    )
    from tagger_app.services.photo_discovery import FileSystemPhotoDiscovery

    photo = tmp_path / "photo.jpg"
    photo.touch()
    path = normalize_path(photo)
    index = PhotoIndex(tmp_path)
    metadata = Metadata()
    metadata.states[path] = KeywordState(["old"], [])

    class Adapter:
        def refresh_folder(self, root, folder):
            return index.refresh_folder(metadata, folder)

        def update_states(self, root, states):
            index.update_states(states)

    runner, events = ManualRunner(), []
    coordinator = BackgroundCoordinator(
        discovery=FileSystemPhotoDiscovery(),
        index=Adapter(),
        runner=runner,
        event_sink=events.append,
    )
    request = coordinator.refresh_folder(
        tmp_path, index_root=tmp_path, workspace_generation=1, candidate_paths=[path]
    )
    duplicate = coordinator.refresh_folder(
        tmp_path, index_root=tmp_path, workspace_generation=1, candidate_paths=[path]
    )
    coordinator.submit_confirmed_states(tmp_path, {path: KeywordState(["new"], [])})
    assert request == duplicate
    runner.drain()
    assert sum(isinstance(e, FolderRefreshCompleted) for e in events) == 1
    assert index.search_photos("tag:new") == [path]


def test_folder_refresh_keeps_full_refresh_checkpoint_resumable(tmp_path):
    from tagger_app.indexing import IndexRefreshProgress

    folder = tmp_path / "birds"
    folder.mkdir()
    photo = folder / "photo.jpg"
    photo.touch()
    metadata = Metadata()
    path = normalize_path(photo)
    metadata.states[path] = KeywordState(["bird"], [])
    index = PhotoIndex(tmp_path)
    first = index.refresh_step(metadata)
    assert isinstance(first, IndexRefreshProgress)
    index.refresh_folder(metadata, folder)
    resumed = index.refresh_step(metadata)
    assert isinstance(resumed, IndexRefreshProgress)
    assert resumed.resumed


def test_checked_discovery_reports_errors_after_partial_enumeration(tmp_path):
    import os
    from tagger_app.services.photo_discovery import FileSystemPhotoDiscovery

    nested = tmp_path / "nested"
    nested.mkdir()
    (tmp_path / "photo.jpg").touch()
    original = os.scandir

    def scandir(path):
        if Path(path) == nested:
            raise PermissionError("nested folder inaccessible")
        return original(path)

    with patch("os.scandir", side_effect=scandir):
        with pytest.raises(PermissionError):
            FileSystemPhotoDiscovery().discover(str(tmp_path))


def test_normal_discovery_keeps_file_links_but_refresh_stays_inside_subtree(tmp_path):
    from tagger_app.services.photo_discovery import FileSystemPhotoDiscovery

    folder = tmp_path / "birds"
    folder.mkdir()
    outside = tmp_path / "outside.jpg"
    outside.touch()
    link = folder / "linked.jpg"
    try:
        link.symlink_to(outside)
    except OSError:
        pytest.skip("File symlinks unavailable")
    discovery = FileSystemPhotoDiscovery()
    assert len(discovery.discover(str(folder))) == 1
    assert discovery.discover_refresh(str(folder)) == []


@pytest.mark.parametrize("redirect_to", ["sibling", "ancestor"])
def test_refresh_never_traverses_redirected_directories_outside_scope(
    tmp_path, redirect_to
):
    import os
    from contextlib import contextmanager
    from tagger_app.services.photo_discovery import FileSystemPhotoDiscovery

    scope, sibling = tmp_path / "birds", tmp_path / "birds-other"
    scope.mkdir()
    sibling.mkdir()
    (sibling / "outside.jpg").touch()
    redirect = scope / "junction"
    try:
        redirect.symlink_to(
            sibling if redirect_to == "sibling" else scope, target_is_directory=True
        )
    except OSError:
        pytest.skip("Directory link fixture unavailable")
    original = os.scandir
    scanned = []

    class Junction:
        # Simulate a Windows junction reported as a non-symlink directory.
        def __init__(self, entry):
            self.path, self.name = entry.path, entry.name

        def is_symlink(self):
            return False

        def is_dir(self, **kwargs):
            return True

    @contextmanager
    def scandir(path):
        scanned.append(Path(path))
        with original(path) as entries:
            yield iter(Junction(e) if Path(e.path) == redirect else e for e in entries)

    with patch("os.scandir", side_effect=scandir):
        paths = FileSystemPhotoDiscovery().discover_refresh(str(scope))
    assert paths == []
    assert scanned == [scope]
