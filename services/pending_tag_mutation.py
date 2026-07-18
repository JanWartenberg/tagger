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

    def fail(self, mutation: PendingTagMutation) -> dict[str, KeywordState]:
        displayed: dict[str, KeywordState] = {}
        for path in mutation.transforms:
            for record in self._records_by_path.get(path, []):
                if record.mutation == mutation:
                    record.status = MutationStatus.FAILED
                    break
            self._recompute_display(path)
            state = self._displayed_states.get(path)
            if state is not None:
                displayed[path] = state
        return displayed

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
