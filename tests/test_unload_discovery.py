from test_background_coordinator import DeterministicRunner, FakeDiscovery, FakeIndex
import pytest

from tagger_app.services.background_coordinator import BackgroundCoordinator
from tagger_app.services.photo_discovery import FileSystemPhotoDiscovery


def test_cancelled_workspace_skips_queued_discovery_and_releases_new_drops(tmp_path):
    runner = DeterministicRunner()
    discovery = FakeDiscovery({})
    events = []
    coordinator = BackgroundCoordinator(
        discovery=discovery, index=FakeIndex(), runner=runner, event_sink=events.append
    )
    old = str(tmp_path / "old")
    new = str(tmp_path / "new")
    discovery.results[old] = [str(tmp_path / "old" / "one.jpg")]
    discovery.results[new] = [str(tmp_path / "new" / "two.jpg")]
    coordinator.replace_workspace_from_folder(old)
    coordinator.add_dropped_directory(old)
    coordinator.unload_workspace()
    coordinator.add_dropped_directory(new)
    while runner.scheduled:
        runner.run()
    assert discovery.requests == [new]
    assert len(events) == 1
    assert events[0].paths == (str(tmp_path / "new" / "two.jpg"),)


def test_filesystem_discovery_stops_at_cancellation_boundary(tmp_path):
    for number in range(5):
        (tmp_path / f"{number}.jpg").touch()
    checks = []

    def cancelled():
        checks.append(True)
        return len(checks) >= 3

    assert (
        FileSystemPhotoDiscovery().discover_cancellable(str(tmp_path), cancelled) == []
    )
    assert len(checks) == 3


@pytest.mark.parametrize("queued", [False, True])
def test_cancelling_index_refresh_preserves_missing_result_repairs(tmp_path, queued):
    runner = DeterministicRunner()
    index = FakeIndex()
    coordinator = BackgroundCoordinator(
        discovery=FakeDiscovery({}),
        index=index,
        runner=runner,
        event_sink=lambda _: None,
    )
    root = str(tmp_path)
    if queued:
        coordinator.ensure_index(root, [])
    coordinator.repair_stale_search_result(
        root, str(tmp_path / "missing.jpg"), workspace_generation=1, query="tag:bird"
    )
    coordinator.cancel_refresh(root)
    while runner.scheduled:
        runner.run()
    assert any(call[0] == "remove" for call in index.calls)
    assert (
        coordinator.repair_stale_search_result(
            root, str(tmp_path / "other.jpg"), workspace_generation=2, query="tag:bird"
        )
        is not None
    )
