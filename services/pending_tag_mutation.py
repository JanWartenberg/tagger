from dataclasses import dataclass
from enum import Enum
from typing import Callable

from exif_tool import KeywordState


class MutationStatus(str, Enum):
    PENDING = "pending"
    FAILED = "failed"


StateTransform = Callable[[KeywordState], KeywordState]


@dataclass(frozen=True)
class PendingTagMutation:
    sequence: int
    transforms: dict[str, StateTransform]


@dataclass
class _MutationRecord:
    mutation: PendingTagMutation
    status: MutationStatus


class PendingTagMutationCoordinator:
    """Tracks confirmed metadata and ordered pending mutations per photo."""

    def __init__(self) -> None:
        self._confirmed_states: dict[str, KeywordState] = {}
        self._displayed_states: dict[str, KeywordState] = {}
        self._records_by_path: dict[str, list[_MutationRecord]] = {}
        self._next_sequence = 0

    def remember_confirmed(self, states: dict[str, KeywordState]) -> None:
        self._confirmed_states.update(states)
        for path in states:
            self._recompute_display(path)

    def begin(self, transforms: dict[str, StateTransform]) -> PendingTagMutation:
        self._next_sequence += 1
        mutation = PendingTagMutation(self._next_sequence, dict(transforms))
        for path in transforms:
            self._records_by_path.setdefault(path, []).append(
                _MutationRecord(mutation, MutationStatus.PENDING)
            )
            self._recompute_display(path)
        return mutation

    def succeed(
        self, mutation: PendingTagMutation, states: dict[str, KeywordState]
    ) -> None:
        self._confirmed_states.update(states)
        for path in states:
            self._remove_record(path, mutation)
            self._recompute_display(path)

    def fail(
        self, mutation: PendingTagMutation, paths: list[str] | None = None
    ) -> dict[str, KeywordState]:
        displayed: dict[str, KeywordState] = {}
        affected_paths = paths if paths is not None else list(mutation.transforms)
        for path in affected_paths:
            for record in self._records_by_path.get(path, []):
                if record.mutation == mutation:
                    record.status = MutationStatus.FAILED
                    break
            self._recompute_display(path)
            state = self._displayed_states.get(path)
            if state is not None:
                displayed[path] = state
        return displayed

    def discard(
        self, mutation: PendingTagMutation, paths: list[str] | None = None
    ) -> None:
        affected_paths = paths if paths is not None else list(mutation.transforms)
        for path in affected_paths:
            self._remove_record(path, mutation)
            self._recompute_display(path)

    def retry_failed(self, paths: list[str]) -> PendingTagMutation | None:
        transforms: dict[str, StateTransform] = {}
        for path in paths:
            failed = [
                record
                for record in self._records_by_path.get(path, [])
                if record.status is MutationStatus.FAILED
            ]
            if not failed:
                continue
            transforms[path] = self._compose_transforms(
                [record.mutation.transforms[path] for record in failed]
            )
            self._records_by_path[path] = [
                record
                for record in self._records_by_path[path]
                if record.status is not MutationStatus.FAILED
            ]
            if not self._records_by_path[path]:
                self._records_by_path.pop(path)
            self._recompute_display(path)

        return self.begin(transforms) if transforms else None

    def metadata_for(self, path: str) -> KeywordState | None:
        return self._displayed_states.get(path)

    def confirmed_for(self, path: str) -> KeywordState | None:
        return self._confirmed_states.get(path)

    def status_for(self, path: str) -> MutationStatus | None:
        records = self._records_by_path.get(path, [])
        if any(record.status is MutationStatus.PENDING for record in records):
            return MutationStatus.PENDING
        if any(record.status is MutationStatus.FAILED for record in records):
            return MutationStatus.FAILED
        return None

    def _compose_transforms(self, transforms: list[StateTransform]) -> StateTransform:
        def _apply(state: KeywordState) -> KeywordState:
            for transform in transforms:
                state = transform(state)
            return state

        return _apply

    def _remove_record(self, path: str, mutation: PendingTagMutation) -> None:
        records = self._records_by_path.get(path, [])
        remaining = [record for record in records if record.mutation != mutation]
        if remaining:
            self._records_by_path[path] = remaining
        else:
            self._records_by_path.pop(path, None)

    def _recompute_display(self, path: str) -> None:
        state = self._confirmed_states.get(path)
        if state is None:
            return
        for record in self._records_by_path.get(path, []):
            if record.status is MutationStatus.PENDING:
                state = record.mutation.transforms[path](state)
        self._displayed_states[path] = state
