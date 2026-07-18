from dataclasses import dataclass
from enum import Enum

from exif_tool import KeywordState


class MutationStatus(str, Enum):
    PENDING = "pending"
    FAILED = "failed"


@dataclass(frozen=True)
class PendingTagMutation:
    confirmed_states: dict[str, KeywordState]


class PendingTagMutationCoordinator:
    """Tracks displayed metadata until a tag write is confirmed or fails."""

    def __init__(self) -> None:
        self._confirmed_states: dict[str, KeywordState] = {}
        self._displayed_states: dict[str, KeywordState] = {}
        self._statuses: dict[str, MutationStatus] = {}

    def remember_confirmed(self, states: dict[str, KeywordState]) -> None:
        self._confirmed_states.update(states)
        for path, state in states.items():
            if path not in self._statuses:
                self._displayed_states[path] = state

    def begin(self, requested_states: dict[str, KeywordState]) -> PendingTagMutation:
        confirmed_states = {
            path: self._confirmed_states[path]
            for path in requested_states
            if path in self._confirmed_states
        }
        mutation = PendingTagMutation(confirmed_states)
        self._displayed_states.update(requested_states)
        self._statuses.update(
            {path: MutationStatus.PENDING for path in requested_states}
        )
        return mutation

    def succeed(
        self, mutation: PendingTagMutation, states: dict[str, KeywordState]
    ) -> None:
        del mutation
        self._confirmed_states.update(states)
        self._displayed_states.update(states)
        for path in states:
            self._statuses.pop(path, None)

    def fail(self, mutation: PendingTagMutation) -> dict[str, KeywordState]:
        self._displayed_states.update(mutation.confirmed_states)
        self._statuses.update(
            {path: MutationStatus.FAILED for path in mutation.confirmed_states}
        )
        return dict(mutation.confirmed_states)

    def metadata_for(self, path: str) -> KeywordState | None:
        return self._displayed_states.get(path)

    def confirmed_for(self, path: str) -> KeywordState | None:
        return self._confirmed_states.get(path)

    def status_for(self, path: str) -> MutationStatus | None:
        return self._statuses.get(path)
