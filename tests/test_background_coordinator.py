from __future__ import annotations

import unittest
from collections.abc import Callable

from services.background_coordinator import (
    BackgroundCoordinator,
    DiscoveryCompleted,
    DiscoveryFailed,
    DiscoveryKind,
    IndexEnsureCompleted,
    IndexOperationKind,
    IndexWriteCompleted,
    IndexWriteFailed,
)


class DeterministicRunner:
    def __init__(self) -> None:
        self.scheduled: list[Callable[[], None]] = []

    def submit(self, work: Callable[[], None]) -> None:
        self.scheduled.append(work)

    def run(self, index: int = 0) -> None:
        self.scheduled.pop(index)()


class FakeIndex:
    def __init__(self) -> None:
        self.initialized: set[str] = set()
        self.calls: list[tuple[str, str, object]] = []
        self.fail_next: set[tuple[str, str]] = set()

    def is_initialized(self, root: str) -> bool:
        self.calls.append(("initialized", root, None))
        return root in self.initialized

    def sync(self, root: str, paths: list[str]) -> object:
        self.calls.append(("sync", root, tuple(paths)))
        if ("sync", root) in self.fail_next:
            self.fail_next.remove(("sync", root))
            raise RuntimeError("sync failed")
        self.initialized.add(root)
        return {"paths": tuple(paths)}

    def index_missing(self, root: str, paths: list[str]) -> int:
        self.calls.append(("missing", root, tuple(paths)))
        return len(paths)

    def update_states(self, root: str, states: dict[str, object]) -> None:
        self.calls.append(("update", root, dict(states)))
        if ("update", root) in self.fail_next:
            self.fail_next.remove(("update", root))
            raise RuntimeError("update failed")

    def search(self, root: str, query: str) -> list[str]:
        del root, query
        return []

    def load_known_tags(self, root: str) -> set[str]:
        del root
        return set()


class FakeDiscovery:
    def __init__(self, results: dict[str, list[str] | Exception]) -> None:
        self.results = results
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
        root = "/photos"
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
                    paths=("/photos/b.jpg", "/photos/a.jpg"),
                    drop_sequence=None,
                )
            ],
        )

    def test_superseded_folder_replacement_discards_its_completion(self) -> None:
        first_root = "/first"
        second_root = "/second"
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
                    paths=("/second/photo.jpg",),
                    drop_sequence=None,
                )
            ],
        )

    def test_superseded_folder_replacement_discards_its_failure(self) -> None:
        first_root = "/first"
        second_root = "/second"
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
                    paths=("/second/photo.jpg",),
                    drop_sequence=None,
                )
            ],
        )

    def test_additive_discoveries_release_in_drop_initiation_order(self) -> None:
        first_root = "/first-drop"
        second_root = "/second-drop"
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
                    paths=("/first-drop/one.jpg",),
                    drop_sequence=0,
                ),
                DiscoveryCompleted(
                    kind=DiscoveryKind.ADDITIVE,
                    workspace_generation=second.workspace_generation,
                    request_id=second.request_id,
                    root=second_root,
                    paths=("/second-drop/two.jpg",),
                    drop_sequence=1,
                ),
            ],
        )

    def test_failed_drop_releases_later_drop_in_initiation_order(self) -> None:
        first_root = "/first-drop"
        second_root = "/second-drop"
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
                    paths=("/second-drop/two.jpg",),
                    drop_sequence=1,
                ),
            ],
        )

    def test_replacement_discards_pending_additive_discovery(self) -> None:
        dropped_root = "/dropped"
        replacement_root = "/replacement"
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
                    paths=("/replacement/photo.jpg",),
                    drop_sequence=None,
                )
            ],
        )


class BackgroundCoordinatorIndexTests(unittest.TestCase):
    def setUp(self) -> None:
        self.events: list[
            IndexEnsureCompleted | IndexWriteCompleted | IndexWriteFailed
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
        self.coordinator.ensure_index("/photos", ["/photos/one.jpg"])

        self.runner.run()

        self.assertEqual(
            self.index.calls,
            [
                ("initialized", "/photos", None),
                ("sync", "/photos", ("/photos/one.jpg",)),
            ],
        )
        self.assertEqual(self.discovery.requests, [])
        self.assertEqual(
            self.events,
            [
                IndexEnsureCompleted(
                    root="/photos",
                    result={"paths": ("/photos/one.jpg",)},
                )
            ],
        )

    def test_different_roots_can_be_scheduled_independently(self) -> None:
        self.coordinator.ensure_index("/first", ["/first/one.jpg"])
        self.coordinator.ensure_index("/second", ["/second/two.jpg"])

        self.assertEqual(len(self.runner.scheduled), 2)
        self.runner.run(1)
        self.runner.run(0)

        self.assertEqual(
            [call[1] for call in self.index.calls if call[0] == "sync"],
            ["/second", "/first"],
        )

    def test_updates_for_one_root_coalesce_to_the_newest_state(self) -> None:
        self.coordinator.ensure_index("/photos", ["/photos/one.jpg"])
        self.coordinator.submit_confirmed_states("/photos", {"/photos/one.jpg": "old"})
        self.coordinator.submit_confirmed_states("/photos", {"/photos/one.jpg": "new"})

        self.runner.run()
        self.runner.run()

        self.assertEqual(
            self.index.calls[-1],
            ("update", "/photos", {"/photos/one.jpg": "new"}),
        )

    def test_confirmed_update_waits_for_full_sync(self) -> None:
        self.coordinator.ensure_index("/photos", ["/photos/one.jpg"])
        self.coordinator.submit_confirmed_states(
            "/photos", {"/photos/one.jpg": "tagged"}
        )

        self.assertEqual(len(self.runner.scheduled), 1)
        self.runner.run()
        self.runner.run()

        self.assertEqual(
            [call[0] for call in self.index.calls],
            ["initialized", "sync", "update"],
        )

    def test_failed_write_does_not_stop_later_work(self) -> None:
        self.index.initialized.add("/photos")
        self.index.fail_next.add(("update", "/photos"))
        self.coordinator.submit_confirmed_states("/photos", {"/photos/one.jpg": "bad"})
        self.coordinator.index_missing_paths("/photos", ["/photos/two.jpg"])

        self.runner.run()
        self.runner.run()

        self.assertEqual([call[0] for call in self.index.calls], ["update", "missing"])
        self.assertIn(
            IndexWriteFailed(
                root="/photos",
                operation=IndexOperationKind.UPDATE_STATES,
                error="update failed",
            ),
            self.events,
        )
        self.assertIn(
            IndexWriteCompleted(
                root="/photos",
                operation=IndexOperationKind.INDEX_MISSING,
            ),
            self.events,
        )


if __name__ == "__main__":
    unittest.main()
