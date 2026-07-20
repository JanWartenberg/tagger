from __future__ import annotations

import unittest
from collections.abc import Callable

from services.background_coordinator import (
    BackgroundCoordinator,
    DiscoveryCompleted,
    DiscoveryFailed,
    DiscoveryKind,
)


class DeterministicRunner:
    def __init__(self) -> None:
        self.scheduled: list[Callable[[], None]] = []

    def submit(self, work: Callable[[], None]) -> None:
        self.scheduled.append(work)

    def run(self, index: int = 0) -> None:
        self.scheduled.pop(index)()


class FakeIndex:
    """Placeholder index adapter; discovery is the only behavior in this slice."""


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
        self.coordinator = BackgroundCoordinator(
            discovery=self.discovery,
            index=FakeIndex(),
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


if __name__ == "__main__":
    unittest.main()
