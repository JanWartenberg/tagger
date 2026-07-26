from __future__ import annotations

import unittest
from collections.abc import Callable

from exif_tool import KeywordState
from services.pending_tag_mutation import MutationStatus, TagIntent
from services.tag_mutation import TagMutationResult
from services.tag_mutation_coordinator import (
    TagMutationCoordinator,
    TagMutationLifecycle,
    TagMutationLifecycleKind,
)


class DeterministicMutationRunner:
    def __init__(self) -> None:
        self.scheduled: list[
            tuple[
                Callable[[], TagMutationResult],
                Callable[[TagMutationResult], None],
                Callable[[str], None],
            ]
        ] = []

    def submit(
        self,
        work: Callable[[], TagMutationResult],
        on_success: Callable[[TagMutationResult], None],
        on_failure: Callable[[str], None],
    ) -> None:
        self.scheduled.append((work, on_success, on_failure))

    def succeed(self, index: int = 0) -> None:
        work, on_success, _on_failure = self.scheduled.pop(index)
        on_success(work())

    def fail(self, error: str, index: int = 0) -> None:
        _work, _on_success, on_failure = self.scheduled.pop(index)
        on_failure(error)


def result(
    updated: dict[str, KeywordState] | None = None,
    failed: dict[str, str] | None = None,
) -> TagMutationResult:
    updated = updated or {}
    return TagMutationResult(
        updated_states=updated,
        emptiness_by_path={path: not state.merged for path, state in updated.items()},
        processed_count=len(updated) + len(failed or {}),
        changed_count=len(updated),
        failed_paths=failed or {},
    )


class TagMutationCoordinatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.events: list[TagMutationLifecycle] = []
        self.runner = DeterministicMutationRunner()
        self.coordinator = TagMutationCoordinator(
            runner=self.runner,
            event_sink=self.events.append,
        )
        self.one = "/photos/one.jpg"
        self.two = "/photos/two.jpg"
        self.confirmed = KeywordState(["confirmed"], ["confirmed"])

    def begin(self, paths: list[str]) -> object:
        return self.coordinator.begin_intents(
            {path: [TagIntent.add("bird")] for path in paths},
            {path: self.confirmed for path in paths},
        )

    def test_serializes_work_and_emits_pending_then_confirmed_facts(self) -> None:
        first = self.begin([self.one])
        second = self.begin([self.two])
        assert first is not None
        assert second is not None
        self.coordinator.enqueue(
            [self.one],
            lambda _paths: result({self.one: KeywordState(["bird"], ["bird"])}),
            first,
        )
        self.coordinator.enqueue(
            [self.two],
            lambda _paths: result({self.two: KeywordState(["bird"], ["bird"])}),
            second,
        )

        self.assertEqual(len(self.runner.scheduled), 1)
        self.runner.succeed()
        self.assertEqual(len(self.runner.scheduled), 1)
        self.runner.succeed()

        self.assertEqual(
            [event.kind for event in self.events],
            [
                TagMutationLifecycleKind.PENDING,
                TagMutationLifecycleKind.PENDING,
                TagMutationLifecycleKind.COMPLETED,
                TagMutationLifecycleKind.COMPLETED,
            ],
        )
        self.assertEqual(self.coordinator.status_for(self.one), None)
        self.assertEqual(self.coordinator.status_for(self.two), None)

    def test_partial_outcome_confirms_success_and_marks_only_failure(self) -> None:
        mutation = self.begin([self.one, self.two])
        assert mutation is not None
        self.coordinator.enqueue(
            [self.one, self.two],
            lambda _paths: result(
                {self.one: KeywordState(["bird"], ["bird"])},
                {self.two: "write failed"},
            ),
            mutation,
        )

        self.runner.succeed()

        event = self.events[-1]
        self.assertEqual(event.kind, TagMutationLifecycleKind.COMPLETED)
        self.assertEqual(
            dict(event.confirmed_states), {self.one: KeywordState(["bird"], ["bird"])}
        )
        self.assertEqual(dict(event.restored_states), {self.two: self.confirmed})
        self.assertEqual(event.failed_paths, (self.two,))
        self.assertEqual(self.coordinator.status_for(self.one), None)
        self.assertEqual(self.coordinator.status_for(self.two), MutationStatus.FAILED)

    def test_retry_replays_failed_intent(self) -> None:
        mutation = self.begin([self.one])
        assert mutation is not None
        self.coordinator.enqueue(
            [self.one],
            lambda _paths: result(failed={self.one: "write failed"}),
            mutation,
        )
        self.runner.succeed()

        retry = self.coordinator.retry_failed([self.one])

        self.assertIsNotNone(retry)
        assert retry is not None
        self.assertEqual(retry.intents_by_path[self.one], (TagIntent.add("bird"),))
        self.assertEqual(self.coordinator.status_for(self.one), MutationStatus.PENDING)
        self.assertEqual(self.events[-1].kind, TagMutationLifecycleKind.PENDING)

    def test_departed_paths_are_discarded_from_queued_work(self) -> None:
        first = self.begin([self.one])
        second = self.begin([self.two])
        assert first is not None
        assert second is not None
        self.coordinator.enqueue([self.one], lambda _paths: result(), first)
        self.coordinator.enqueue([self.two], lambda _paths: result(), second)

        generation = self.coordinator.replace_workspace([self.one])
        self.runner.succeed()

        self.assertEqual(generation, 1)
        self.assertEqual(self.coordinator.status_for(self.two), None)
        self.assertEqual(self.runner.scheduled, [])

    def test_inflight_completion_updates_state_but_cannot_render_replacement(
        self,
    ) -> None:
        mutation = self.begin([self.one])
        assert mutation is not None
        self.coordinator.enqueue(
            [self.one],
            lambda _paths: result({self.one: KeywordState(["bird"], ["bird"])}),
            mutation,
        )
        self.coordinator.replace_workspace([])

        self.runner.succeed()

        event = self.events[-1]
        self.assertEqual(event.kind, TagMutationLifecycleKind.COMPLETED)
        self.assertFalse(event.render_workspace)
        self.assertEqual(
            self.coordinator.confirmed_for(self.one), KeywordState(["bird"], ["bird"])
        )

    def test_runner_failure_restores_confirmed_metadata(self) -> None:
        mutation = self.begin([self.one])
        assert mutation is not None
        self.coordinator.enqueue([self.one], lambda _paths: result(), mutation)

        self.runner.fail("executor failed")

        event = self.events[-1]
        self.assertEqual(event.kind, TagMutationLifecycleKind.FAILED)
        self.assertEqual(dict(event.restored_states), {self.one: self.confirmed})
        self.assertEqual(event.error, "executor failed")
        self.assertEqual(self.coordinator.status_for(self.one), MutationStatus.FAILED)


if __name__ == "__main__":
    unittest.main()
