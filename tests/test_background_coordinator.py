from __future__ import annotations

import unittest
from collections.abc import Callable
from unittest.mock import patch

from indexing import IndexRefreshProgress as RefreshStep
from services.background_coordinator import (
    BackgroundCoordinator,
    DiscoveryCompleted,
    DiscoveryFailed,
    DiscoveryKind,
    IndexEnsureCompleted,
    IndexOperationKind,
    IndexRefreshCompleted,
    IndexRefreshProgress,
    IndexRefreshFailed,
    IndexRefreshKind,
    IndexSearchCompleted,
    KnownTagsCompleted,
    IndexWriteCompleted,
    IndexWriteFailed,
)
from utils import normalize_path


def fixture_path(path: str) -> str:
    """Return a platform-native absolute path for an adapter fixture."""
    return normalize_path(path)


class _DiscoveryResults(dict[str, list[str] | Exception]):
    def __setitem__(self, root: str, result: list[str] | Exception) -> None:
        normalized_result = (
            [fixture_path(path) for path in result]
            if isinstance(result, list)
            else result
        )
        super().__setitem__(fixture_path(root), normalized_result)


class DeterministicRunner:
    def __init__(self) -> None:
        self.scheduled: list[Callable[[], None]] = []

    def submit(self, work: Callable[[], None]) -> None:
        self.scheduled.append(work)

    def run(self, index: int = 0) -> None:
        self.scheduled.pop(index)()


class IncompleteRefresh:
    complete = False


class FakeIndex:
    def __init__(self) -> None:
        self.initialized: set[str] = set()
        self.stale: set[str] = set()
        self.keyword_rebuilds: set[str] = set()
        self.calls: list[tuple[str, str, object]] = []
        self.fail_next: set[tuple[str, str]] = set()
        self.search_results: dict[tuple[str, str], list[str]] = {}
        self.known_tags: dict[str, set[str]] = {}
        self.refresh_results: list[object] = []

    def is_initialized(self, root: str) -> bool:
        self.calls.append(("initialized", root, None))
        return root in self.initialized

    def needs_keyword_index_rebuild(self, root: str) -> bool:
        self.calls.append(("keyword_rebuild", root, None))
        return root in self.keyword_rebuilds

    def is_refresh_stale(self, root: str) -> bool:
        self.calls.append(("stale", root, None))
        return root in self.stale

    def sync(self, root: str, paths: list[str]) -> object:
        self.calls.append(("sync", root, tuple(paths)))
        if ("sync", root) in self.fail_next:
            self.fail_next.remove(("sync", root))
            raise RuntimeError("sync failed")
        self.initialized.add(root)
        return {"paths": tuple(paths)}

    def refresh(self, root: str) -> object:
        self.calls.append(("refresh", root, None))
        if ("refresh", root) in self.fail_next:
            self.fail_next.remove(("refresh", root))
            raise RuntimeError("refresh failed")
        self.stale.discard(root)
        result = (
            self.refresh_results.pop(0) if self.refresh_results else {"refreshed": root}
        )
        if getattr(result, "complete", True):
            self.keyword_rebuilds.discard(root)
            self.initialized.add(root)
        return result

    def cancel_refresh(self, root: str) -> bool:
        self.calls.append(("cancel", root, None))
        return True

    def remove_photo(self, root: str, path: str) -> bool:
        self.calls.append(("remove", root, path))
        if ("remove", root) in self.fail_next:
            self.fail_next.remove(("remove", root))
            raise RuntimeError("remove failed")
        return True

    def reconcile_directory(self, root: str, directory: str) -> object:
        self.calls.append(("directory", root, directory))
        if ("directory", root) in self.fail_next:
            self.fail_next.remove(("directory", root))
            raise RuntimeError("directory failed")
        return {"directory": directory}

    def index_missing(self, root: str, paths: list[str]) -> int:
        self.calls.append(("missing", root, tuple(paths)))
        return len(paths)

    def update_states(self, root: str, states: dict[str, object]) -> None:
        self.calls.append(("update", root, dict(states)))
        if ("update", root) in self.fail_next:
            self.fail_next.remove(("update", root))
            raise RuntimeError("update failed")

    def search(self, root: str, query: str) -> list[str]:
        self.calls.append(("search", root, query))
        return self.search_results.get((root, query), [])

    def load_known_tags(self, root: str) -> set[str]:
        self.calls.append(("known", root, None))
        return self.known_tags.get(root, set())


class FakeDiscovery:
    def __init__(self, results: dict[str, list[str] | Exception]) -> None:
        self.results = _DiscoveryResults()
        for root, result in results.items():
            self.results[root] = result
        self.requests: list[str] = []

    def discover(self, root: str) -> list[str]:
        self.requests.append(root)
        result = self.results[root]
        if isinstance(result, Exception):
            raise result
        return result


class BackgroundCoordinatorDiscoveryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.events: list[DiscoveryCompleted | DiscoveryFailed] = []
        self.runner = DeterministicRunner()
        self.discovery = FakeDiscovery({})
        self.index = FakeIndex()
        self.coordinator = BackgroundCoordinator(
            discovery=self.discovery,
            index=self.index,
            runner=self.runner,
            event_sink=self.events.append,
        )

    def test_current_folder_replacement_emits_its_normalized_ordered_paths(
        self,
    ) -> None:
        root = fixture_path("/photos")
        self.discovery.results[root] = ["/photos/./b.jpg", "/photos/a.jpg"]

        request = self.coordinator.replace_workspace_from_folder(root)
        self.runner.run()

        self.assertEqual(
            self.events,
            [
                DiscoveryCompleted(
                    kind=DiscoveryKind.REPLACEMENT,
                    workspace_generation=request.workspace_generation,
                    request_id=request.request_id,
                    root=root,
                    paths=(
                        fixture_path("/photos/b.jpg"),
                        fixture_path("/photos/a.jpg"),
                    ),
                    drop_sequence=None,
                )
            ],
        )

    def test_superseded_folder_replacement_discards_its_completion(self) -> None:
        first_root = fixture_path("/first")
        second_root = fixture_path("/second")
        self.discovery.results[first_root] = ["/first/photo.jpg"]
        self.discovery.results[second_root] = ["/second/photo.jpg"]

        self.coordinator.replace_workspace_from_folder(first_root)
        current = self.coordinator.replace_workspace_from_folder(second_root)
        self.runner.run(0)
        self.runner.run(0)

        self.assertEqual(
            self.events,
            [
                DiscoveryCompleted(
                    kind=DiscoveryKind.REPLACEMENT,
                    workspace_generation=current.workspace_generation,
                    request_id=current.request_id,
                    root=second_root,
                    paths=(fixture_path("/second/photo.jpg"),),
                    drop_sequence=None,
                )
            ],
        )

    def test_superseded_folder_replacement_discards_its_failure(self) -> None:
        first_root = fixture_path("/first")
        second_root = fixture_path("/second")
        self.discovery.results[first_root] = RuntimeError("unavailable")
        self.discovery.results[second_root] = ["/second/photo.jpg"]

        self.coordinator.replace_workspace_from_folder(first_root)
        current = self.coordinator.replace_workspace_from_folder(second_root)
        self.runner.run(0)
        self.runner.run(0)

        self.assertEqual(
            self.events,
            [
                DiscoveryCompleted(
                    kind=DiscoveryKind.REPLACEMENT,
                    workspace_generation=current.workspace_generation,
                    request_id=current.request_id,
                    root=second_root,
                    paths=(fixture_path("/second/photo.jpg"),),
                    drop_sequence=None,
                )
            ],
        )

    def test_additive_discoveries_release_in_drop_initiation_order(self) -> None:
        first_root = fixture_path("/first-drop")
        second_root = fixture_path("/second-drop")
        self.discovery.results[first_root] = ["/first-drop/one.jpg"]
        self.discovery.results[second_root] = ["/second-drop/two.jpg"]

        first = self.coordinator.add_dropped_directory(first_root)
        second = self.coordinator.add_dropped_directory(second_root)
        self.runner.run(1)
        self.assertEqual(self.events, [])

        self.runner.run(0)

        self.assertEqual(
            self.events,
            [
                DiscoveryCompleted(
                    kind=DiscoveryKind.ADDITIVE,
                    workspace_generation=first.workspace_generation,
                    request_id=first.request_id,
                    root=first_root,
                    paths=(fixture_path("/first-drop/one.jpg"),),
                    drop_sequence=0,
                ),
                DiscoveryCompleted(
                    kind=DiscoveryKind.ADDITIVE,
                    workspace_generation=second.workspace_generation,
                    request_id=second.request_id,
                    root=second_root,
                    paths=(fixture_path("/second-drop/two.jpg"),),
                    drop_sequence=1,
                ),
            ],
        )

    def test_failed_drop_releases_later_drop_in_initiation_order(self) -> None:
        first_root = fixture_path("/first-drop")
        second_root = fixture_path("/second-drop")
        self.discovery.results[first_root] = RuntimeError("unavailable")
        self.discovery.results[second_root] = ["/second-drop/two.jpg"]

        first = self.coordinator.add_dropped_directory(first_root)
        second = self.coordinator.add_dropped_directory(second_root)
        self.runner.run(1)
        self.assertEqual(self.events, [])

        self.runner.run(0)

        self.assertEqual(
            self.events,
            [
                DiscoveryFailed(
                    kind=DiscoveryKind.ADDITIVE,
                    workspace_generation=first.workspace_generation,
                    request_id=first.request_id,
                    root=first_root,
                    error="unavailable",
                    drop_sequence=0,
                ),
                DiscoveryCompleted(
                    kind=DiscoveryKind.ADDITIVE,
                    workspace_generation=second.workspace_generation,
                    request_id=second.request_id,
                    root=second_root,
                    paths=(fixture_path("/second-drop/two.jpg"),),
                    drop_sequence=1,
                ),
            ],
        )

    def test_replacement_discards_pending_additive_discovery(self) -> None:
        dropped_root = fixture_path("/dropped")
        replacement_root = fixture_path("/replacement")
        self.discovery.results[dropped_root] = ["/dropped/photo.jpg"]
        self.discovery.results[replacement_root] = ["/replacement/photo.jpg"]

        self.coordinator.add_dropped_directory(dropped_root)
        replacement = self.coordinator.replace_workspace_from_folder(replacement_root)
        self.runner.run(0)
        self.runner.run(0)

        self.assertEqual(
            self.events,
            [
                DiscoveryCompleted(
                    kind=DiscoveryKind.REPLACEMENT,
                    workspace_generation=replacement.workspace_generation,
                    request_id=replacement.request_id,
                    root=replacement_root,
                    paths=(fixture_path("/replacement/photo.jpg"),),
                    drop_sequence=None,
                )
            ],
        )


class BackgroundCoordinatorIndexTests(unittest.TestCase):
    def setUp(self) -> None:
        self.events: list[
            IndexEnsureCompleted
            | IndexWriteCompleted
            | IndexWriteFailed
            | IndexRefreshCompleted
            | IndexRefreshFailed
        ] = []
        self.runner = DeterministicRunner()
        self.index = FakeIndex()
        self.discovery = FakeDiscovery({})
        self.coordinator = BackgroundCoordinator(
            discovery=self.discovery,
            index=self.index,
            runner=self.runner,
            event_sink=self.events.append,
        )

    def test_initial_sync_reuses_the_discovered_paths(self) -> None:
        root = fixture_path("/photos")
        photo = fixture_path("/photos/one.jpg")
        self.coordinator.ensure_index(root, [photo])

        self.runner.run()

        self.assertEqual(
            self.index.calls,
            [
                ("initialized", root, None),
                ("keyword_rebuild", root, None),
                ("sync", root, (photo,)),
            ],
        )
        self.assertEqual(self.discovery.requests, [])
        self.assertEqual(
            self.events,
            [IndexEnsureCompleted(root=root, result={"paths": (photo,)})],
        )

    def test_initial_sync_accepts_normalized_discovery_paths_without_repeating_io(
        self,
    ) -> None:
        root = fixture_path("/photos")
        paths = [fixture_path(f"/photos/{number}.jpg") for number in range(2)]

        with patch(
            "services.background_coordinator._normalize_path",
            wraps=normalize_path,
        ) as normalize:
            self.coordinator.ensure_index(root, paths, paths_are_normalized=True)

        normalize.assert_called_once_with(root)
        self.runner.run()
        self.assertIn(("sync", root, tuple(paths)), self.index.calls)

    def test_keyword_index_rebuild_continues_as_resumable_ensure_work(self) -> None:
        root = fixture_path("/photos")
        photo = fixture_path("/photos/one.jpg")
        self.index.keyword_rebuilds.add(root)
        self.index.refresh_results = [IncompleteRefresh(), {"rebuilt": root}]

        self.coordinator.ensure_index(root, [photo])
        self.runner.run()

        self.assertEqual(
            [call[0] for call in self.index.calls],
            ["initialized", "keyword_rebuild", "refresh"],
        )
        self.assertEqual(len(self.runner.scheduled), 1)
        self.assertIsInstance(self.events[0], IndexEnsureCompleted)
        self.assertIsInstance(self.events[0].result, IncompleteRefresh)

        self.runner.run()

        self.assertEqual(
            [call[0] for call in self.index.calls],
            [
                "initialized",
                "keyword_rebuild",
                "refresh",
                "initialized",
                "keyword_rebuild",
                "refresh",
            ],
        )
        self.assertEqual(
            self.events[-1], IndexEnsureCompleted(root=root, result={"rebuilt": root})
        )

    def test_cancel_removes_queued_keyword_index_rebuild_continuation(self) -> None:
        root = fixture_path("/photos")
        photo = fixture_path("/photos/one.jpg")
        self.index.keyword_rebuilds.add(root)
        self.index.refresh_results = [IncompleteRefresh()]

        self.coordinator.ensure_index(root, [photo])
        self.runner.run()
        self.coordinator.cancel_refresh(root)
        self.runner.run()
        self.runner.run()

        self.assertEqual(
            [call[0] for call in self.index.calls],
            ["initialized", "keyword_rebuild", "refresh", "cancel"],
        )
        self.assertEqual(self.runner.scheduled, [])

    def test_read_runs_without_waiting_for_a_root_write(self) -> None:
        root = fixture_path("/photos")
        photo = fixture_path("/photos/one.jpg")
        self.coordinator.ensure_index(root, [photo])
        self.index.search_results[(root, "tag:bird")] = [photo]
        request = self.coordinator.search_index(
            root, "tag:bird", workspace_generation=4
        )

        self.assertEqual(len(self.runner.scheduled), 2)
        self.runner.run(1)

        self.assertEqual(
            self.events,
            [IndexSearchCompleted(request=request, paths=(photo,))],
        )

    def test_superseded_search_does_not_emit_a_ui_eligible_result(self) -> None:
        root = fixture_path("/photos")
        self.index.search_results[(root, "first")] = [fixture_path("/photos/first.jpg")]
        second_photo = fixture_path("/photos/second.jpg")
        self.index.search_results[(root, "second")] = [second_photo]

        self.coordinator.search_index(root, "first", workspace_generation=4)
        current = self.coordinator.search_index(root, "second", workspace_generation=4)
        self.runner.run(0)
        self.runner.run(0)

        self.assertEqual(
            self.events,
            [IndexSearchCompleted(request=current, paths=(second_photo,))],
        )

    def test_superseded_known_tag_refresh_does_not_emit_a_result(self) -> None:
        first_root = fixture_path("/first")
        second_root = fixture_path("/second")
        self.index.known_tags[first_root] = {"first"}
        self.index.known_tags[second_root] = {"second"}

        self.coordinator.load_known_tags(first_root, workspace_generation=1)
        current = self.coordinator.load_known_tags(second_root, workspace_generation=2)
        self.runner.run(0)
        self.runner.run(0)

        self.assertEqual(
            self.events,
            [KnownTagsCompleted(request=current, tags=frozenset({"second"}))],
        )

    def test_different_roots_can_be_scheduled_independently(self) -> None:
        first_root = fixture_path("/first")
        second_root = fixture_path("/second")
        self.coordinator.ensure_index(first_root, [fixture_path("/first/one.jpg")])
        self.coordinator.ensure_index(second_root, [fixture_path("/second/two.jpg")])

        self.assertEqual(len(self.runner.scheduled), 2)
        self.runner.run(1)
        self.runner.run(0)

        self.assertEqual(
            [call[1] for call in self.index.calls if call[0] == "sync"],
            [second_root, first_root],
        )

    def test_updates_for_one_root_coalesce_to_the_newest_state(self) -> None:
        root = fixture_path("/photos")
        photo = fixture_path("/photos/one.jpg")
        self.coordinator.ensure_index(root, [photo])
        self.coordinator.submit_confirmed_states(root, {photo: "old"})
        self.coordinator.submit_confirmed_states(root, {photo: "new"})

        self.runner.run()
        self.runner.run()

        self.assertEqual(self.index.calls[-1], ("update", root, {photo: "new"}))

    def test_confirmed_update_waits_for_full_sync(self) -> None:
        root = fixture_path("/photos")
        photo = fixture_path("/photos/one.jpg")
        self.coordinator.ensure_index(root, [photo])
        self.coordinator.submit_confirmed_states(root, {photo: "tagged"})

        self.assertEqual(len(self.runner.scheduled), 1)
        self.runner.run()
        self.runner.run()

        self.assertEqual(
            [call[0] for call in self.index.calls],
            ["initialized", "keyword_rebuild", "sync", "update"],
        )

    def test_stale_index_refreshes_in_the_serial_root_queue(self) -> None:
        root = fixture_path("/photos")
        photo = fixture_path("/photos/one.jpg")
        self.index.initialized.add(root)
        self.index.stale.add(root)

        request = self.coordinator.refresh_if_stale(root, workspace_generation=7)
        self.coordinator.submit_confirmed_states(root, {photo: "tagged"})
        self.runner.run()
        self.runner.run()

        self.assertEqual(
            [call[0] for call in self.index.calls], ["stale", "refresh", "update"]
        )
        self.assertIn(
            IndexRefreshCompleted(request=request, result={"refreshed": root}),
            self.events,
        )

    def test_real_refresh_progress_schedules_the_next_chunk(self) -> None:
        root = fixture_path("/photos")
        self.index.refresh_results = [
            RefreshStep(root, "discovering", 1_000, 1_000),
            {"refreshed": root},
        ]

        request = self.coordinator.reindex(root, workspace_generation=3)
        self.runner.run()

        self.assertEqual(
            self.events,
            [
                IndexRefreshProgress(
                    request,
                    RefreshStep(root, "discovering", 1_000, 1_000),
                )
            ],
        )
        self.assertEqual(len(self.runner.scheduled), 1)

        self.runner.run()
        self.assertIn(
            IndexRefreshCompleted(request=request, result={"refreshed": root}),
            self.events,
        )

    def test_refresh_chunk_yields_to_confirmed_updates_before_continuing(self) -> None:
        root = fixture_path("/photos")
        photo = fixture_path("/photos/one.jpg")
        self.index.refresh_results = [IncompleteRefresh(), {"refreshed": root}]

        self.coordinator.reindex(root, workspace_generation=3)
        self.coordinator.submit_confirmed_states(root, {photo: "tagged"})
        self.runner.run()
        self.runner.run()
        self.runner.run()

        self.assertEqual(
            [call[0] for call in self.index.calls], ["refresh", "update", "refresh"]
        )
        self.assertTrue(
            any(isinstance(event, IndexRefreshCompleted) for event in self.events)
        )

    def test_fresh_automatic_refresh_reports_no_work(self) -> None:
        root = fixture_path("/photos")
        request = self.coordinator.refresh_if_stale(root, workspace_generation=3)

        self.runner.run()

        self.assertEqual(self.index.calls, [("stale", root, None)])
        self.assertEqual(
            self.events,
            [IndexRefreshCompleted(request=request, result=None)],
        )

    def test_stale_result_repair_is_deduplicated_and_serializes_later_updates(
        self,
    ) -> None:
        root = fixture_path("/photos")
        photo = fixture_path("/photos/one.jpg")

        request = self.coordinator.repair_stale_search_result(
            root, photo, workspace_generation=5, query="tag:bird"
        )
        duplicate = self.coordinator.repair_stale_search_result(
            root, photo, workspace_generation=5, query="tag:bird"
        )
        self.coordinator.submit_confirmed_states(root, {photo: "tagged"})
        self.runner.run()
        self.runner.run()

        self.assertEqual(request.kind, IndexRefreshKind.STALE_RESULT_REPAIR)
        self.assertIsNone(duplicate)
        self.assertEqual(
            [call[0] for call in self.index.calls], ["remove", "directory", "update"]
        )
        self.assertIn(
            IndexRefreshCompleted(
                request=request, result={"directory": fixture_path("/photos")}
            ),
            self.events,
        )

    def test_stale_result_repair_waits_for_previously_queued_root_writes(self) -> None:
        root = fixture_path("/photos")
        photo = fixture_path("/photos/one.jpg")

        self.coordinator.submit_confirmed_states(root, {photo: "before-repair"})
        self.coordinator.repair_stale_search_result(
            root, photo, workspace_generation=5, query="tag:bird"
        )
        self.runner.run()
        self.runner.run()

        self.assertEqual(
            [call[0] for call in self.index.calls], ["update", "remove", "directory"]
        )

    def test_failed_stale_result_repair_allows_a_later_repair(self) -> None:
        root = fixture_path("/photos")
        self.index.fail_next.add(("remove", root))
        photo = fixture_path("/photos/one.jpg")

        request = self.coordinator.repair_stale_search_result(
            root, photo, workspace_generation=5, query="tag:bird"
        )
        self.runner.run()
        retry = self.coordinator.repair_stale_search_result(
            root, photo, workspace_generation=5, query="tag:bird"
        )

        self.assertIn(
            IndexRefreshFailed(request=request, error="remove failed"), self.events
        )
        self.assertIsNotNone(retry)

    def test_manual_reindex_failure_does_not_stop_later_writes(self) -> None:
        root = fixture_path("/photos")
        photo = fixture_path("/photos/one.jpg")
        self.index.fail_next.add(("refresh", root))
        request = self.coordinator.reindex(root, workspace_generation=5)
        self.coordinator.submit_confirmed_states(root, {photo: "tagged"})

        self.runner.run()
        self.runner.run()

        self.assertEqual([call[0] for call in self.index.calls], ["refresh", "update"])
        self.assertIn(
            IndexRefreshFailed(request=request, error="refresh failed"), self.events
        )
        self.assertIn(
            IndexWriteCompleted(root=root, operation=IndexOperationKind.UPDATE_STATES),
            self.events,
        )

    def test_failed_write_does_not_stop_later_work(self) -> None:
        root = fixture_path("/photos")
        photo = fixture_path("/photos/one.jpg")
        self.index.initialized.add(root)
        self.index.fail_next.add(("update", root))
        self.coordinator.submit_confirmed_states(root, {photo: "bad"})
        self.coordinator.index_missing_paths(root, [fixture_path("/photos/two.jpg")])

        self.runner.run()
        self.runner.run()

        self.assertEqual([call[0] for call in self.index.calls], ["update", "missing"])
        self.assertIn(
            IndexWriteFailed(
                root=root,
                operation=IndexOperationKind.UPDATE_STATES,
                error="update failed",
            ),
            self.events,
        )
        self.assertIn(
            IndexWriteCompleted(root=root, operation=IndexOperationKind.INDEX_MISSING),
            self.events,
        )


if __name__ == "__main__":
    unittest.main()
