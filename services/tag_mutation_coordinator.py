"""Qt-free queueing and lifecycle coordination for tag mutations."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from exif_tool import KeywordState
from services.pending_tag_mutation import (
    MutationStatus,
    PendingTagMutation,
    PendingTagMutationCoordinator,
    TagIntent,
)
from services.tag_mutation import TagMutationResult


class TagMutationRunner(Protocol):
    """Runs a mutation away from the caller and reports its terminal outcome."""

    def submit(
        self,
        work: Callable[[], TagMutationResult],
        on_success: Callable[[TagMutationResult], None],
        on_failure: Callable[[str], None],
    ) -> None: ...


class TagMutationLifecycleKind(Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(frozen=True)
class TagMutationLifecycle:
    """Immutable state fact emitted whenever a mutation lifecycle changes."""

    kind: TagMutationLifecycleKind
    mutation: PendingTagMutation | None
    workspace_generation: int
    render_workspace: bool
    displayed_states: tuple[tuple[str, KeywordState], ...] = ()
    confirmed_states: tuple[tuple[str, KeywordState], ...] = ()
    restored_states: tuple[tuple[str, KeywordState], ...] = ()
    emptiness_by_path: tuple[tuple[str, bool], ...] = ()
    failed_paths: tuple[str, ...] = ()
    status_message: str | None = None
    error: str | None = None


@dataclass(frozen=True)
class _QueuedTagMutation:
    paths: tuple[str, ...]
    work: Callable[[list[str]], TagMutationResult]
    status_message: str | None
    pending_mutation: PendingTagMutation | None
    workspace_generation: int


class TagMutationCoordinator:
    """Own serialized tag writes and their pending/failed metadata lifecycle."""

    def __init__(
        self,
        *,
        runner: TagMutationRunner,
        event_sink: Callable[[TagMutationLifecycle], None],
    ) -> None:
        self._runner = runner
        self._event_sink = event_sink
        self._pending = PendingTagMutationCoordinator()
        self._queue: list[_QueuedTagMutation] = []
        self._inflight = False
        self._workspace_generation = 0

    @property
    def workspace_generation(self) -> int:
        return self._workspace_generation

    def remember_confirmed(self, states: Mapping[str, KeywordState]) -> None:
        self._pending.remember_confirmed(dict(states))

    def confirmed_for(self, path: str) -> KeywordState | None:
        return self._pending.confirmed_for(path)

    def metadata_for(self, path: str) -> KeywordState | None:
        return self._pending.metadata_for(path)

    def status_for(self, path: str) -> MutationStatus | None:
        return self._pending.status_for(path)

    def begin_intents(
        self,
        intents_by_path: Mapping[str, Sequence[TagIntent]],
        confirmed_states: Mapping[str, KeywordState],
    ) -> PendingTagMutation | None:
        missing_confirmed = {
            path: state
            for path, state in confirmed_states.items()
            if self._pending.confirmed_for(path) is None
        }
        self._pending.remember_confirmed(missing_confirmed)
        mutation = self._pending.begin_intents(
            {path: list(intents) for path, intents in intents_by_path.items()}
        )
        if not mutation.intents_by_path:
            return None
        self._emit_pending(mutation)
        return mutation

    def retry_failed(self, paths: Sequence[str]) -> PendingTagMutation | None:
        mutation = self._pending.retry_failed(list(paths))
        if mutation is not None:
            self._emit_pending(mutation)
        return mutation

    def enqueue(
        self,
        paths: Sequence[str],
        work: Callable[[list[str]], TagMutationResult],
        pending_mutation: PendingTagMutation | None,
        status_message: str | None = None,
    ) -> None:
        self._queue.append(
            _QueuedTagMutation(
                tuple(paths),
                work,
                status_message,
                pending_mutation,
                self._workspace_generation,
            )
        )
        self._process_queue()

    def replace_workspace(self, paths: Sequence[str]) -> int:
        """Discard departed queued intent and invalidate in-flight UI rendering."""
        replacement_paths = set(paths)
        self._workspace_generation += 1
        surviving: list[_QueuedTagMutation] = []
        for queued in self._queue:
            retained_paths = tuple(
                path for path in queued.paths if path in replacement_paths
            )
            departed_paths = [
                path for path in queued.paths if path not in replacement_paths
            ]
            if departed_paths and queued.pending_mutation is not None:
                self._pending.discard(queued.pending_mutation, departed_paths)
            if retained_paths:
                surviving.append(
                    _QueuedTagMutation(
                        retained_paths,
                        queued.work,
                        queued.status_message,
                        queued.pending_mutation,
                        self._workspace_generation,
                    )
                )
        self._queue = surviving
        return self._workspace_generation

    def _emit_pending(self, mutation: PendingTagMutation) -> None:
        displayed = tuple(
            (path, state)
            for path in mutation.intents_by_path
            if (state := self._pending.metadata_for(path)) is not None
        )
        self._event_sink(
            TagMutationLifecycle(
                TagMutationLifecycleKind.PENDING,
                mutation,
                self._workspace_generation,
                True,
                displayed_states=displayed,
            )
        )

    def _process_queue(self) -> None:
        if self._inflight or not self._queue:
            return
        self._inflight = True
        queued = self._queue.pop(0)

        def work() -> TagMutationResult:
            return queued.work(list(queued.paths))

        self._runner.submit(
            work,
            lambda result: self._complete(queued, result),
            lambda error: self._fail(queued, error),
        )

    def _complete(self, queued: _QueuedTagMutation, result: TagMutationResult) -> None:
        self._inflight = False
        restored: dict[str, KeywordState] = {}
        if queued.pending_mutation is None:
            self._pending.remember_confirmed(result.updated_states)
        else:
            self._pending.succeed(queued.pending_mutation, result.updated_states)
            restored = self._pending.fail(
                queued.pending_mutation,
                list(result.failed_paths),
                result.attempts_by_path,
            )
        render_workspace = queued.workspace_generation == self._workspace_generation
        self._event_sink(
            TagMutationLifecycle(
                TagMutationLifecycleKind.COMPLETED,
                queued.pending_mutation,
                queued.workspace_generation,
                render_workspace,
                confirmed_states=tuple(result.updated_states.items()),
                restored_states=tuple(restored.items()),
                emptiness_by_path=tuple(result.emptiness_by_path.items()),
                failed_paths=tuple(result.failed_paths),
                status_message=queued.status_message,
            )
        )
        self._process_queue()

    def _fail(self, queued: _QueuedTagMutation, error: str) -> None:
        self._inflight = False
        restored: dict[str, KeywordState] = {}
        if queued.pending_mutation is not None:
            restored = self._pending.fail(queued.pending_mutation)
        render_workspace = queued.workspace_generation == self._workspace_generation
        self._event_sink(
            TagMutationLifecycle(
                TagMutationLifecycleKind.FAILED,
                queued.pending_mutation,
                queued.workspace_generation,
                render_workspace,
                restored_states=tuple(restored.items()),
                error=error,
            )
        )
        self._process_queue()
