from dataclasses import dataclass
from enum import Enum

from exif_tool import KeywordState
from utils import dedupe_casefold


class MutationStatus(str, Enum):
    PENDING = "pending"
    FAILED = "failed"


class TagIntentKind(str, Enum):
    ADD = "add"
    REMOVE = "remove"


@dataclass(frozen=True)
class TagIntent:
    """One requested change to a case-insensitive tag identity."""

    kind: TagIntentKind
    tag: str

    @classmethod
    def add(cls, tag: str) -> "TagIntent":
        return cls(TagIntentKind.ADD, tag.strip())

    @classmethod
    def remove(cls, tag: str) -> "TagIntent":
        return cls(TagIntentKind.REMOVE, tag.strip())

    @property
    def identity(self) -> str:
        return self.tag.casefold()


@dataclass(frozen=True)
class PendingTagMutation:
    sequence: int
    intents_by_path: dict[str, tuple[TagIntent, ...]]

    def apply(self, path: str, state: KeywordState) -> KeywordState:
        return apply_tag_intents(state, self.intents_by_path[path])


@dataclass
class _MutationRecord:
    mutation: PendingTagMutation
    status: MutationStatus
    intents: tuple[TagIntent, ...]


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

    def begin_intents(
        self, intents_by_path: dict[str, list[TagIntent]]
    ) -> PendingTagMutation:
        """Record requested intent and supersede matching failed intent per path."""
        normalized = {
            path: self._normalize_intents(intents)
            for path, intents in intents_by_path.items()
        }
        normalized = {path: intents for path, intents in normalized.items() if intents}
        self._next_sequence += 1
        mutation = PendingTagMutation(self._next_sequence, normalized)
        for path, intents in normalized.items():
            self._supersede_failed_intents(path, intents)
            self._records_by_path.setdefault(path, []).append(
                _MutationRecord(mutation, MutationStatus.PENDING, intents)
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
        affected_paths = paths if paths is not None else list(mutation.intents_by_path)
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
        """Discard queued intent, but retain failed session-only attention state."""
        affected_paths = paths if paths is not None else list(mutation.intents_by_path)
        for path in affected_paths:
            records = self._records_by_path.get(path, [])
            remaining = [
                record
                for record in records
                if record.mutation != mutation or record.status is MutationStatus.FAILED
            ]
            if remaining:
                self._records_by_path[path] = remaining
            else:
                self._records_by_path.pop(path, None)
            self._recompute_display(path)

    def retry_failed(self, paths: list[str]) -> PendingTagMutation | None:
        intents_by_path: dict[str, list[TagIntent]] = {}
        for path in paths:
            failed = [
                record
                for record in self._records_by_path.get(path, [])
                if record.status is MutationStatus.FAILED
            ]
            if not failed:
                continue
            intents_by_path[path] = [
                intent for record in failed for intent in record.intents
            ]
            self._records_by_path[path] = [
                record
                for record in self._records_by_path[path]
                if record.status is not MutationStatus.FAILED
            ]
            if not self._records_by_path[path]:
                self._records_by_path.pop(path)
            self._recompute_display(path)

        return self._begin_intents(intents_by_path, supersede_failed=False)

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

    def _begin_intents(
        self,
        intents_by_path: dict[str, list[TagIntent]],
        *,
        supersede_failed: bool,
    ) -> PendingTagMutation | None:
        normalized = {
            path: self._normalize_intents(intents)
            for path, intents in intents_by_path.items()
        }
        normalized = {path: intents for path, intents in normalized.items() if intents}
        if not normalized:
            return None
        self._next_sequence += 1
        mutation = PendingTagMutation(self._next_sequence, normalized)
        for path, intents in normalized.items():
            if supersede_failed:
                self._supersede_failed_intents(path, intents)
            self._records_by_path.setdefault(path, []).append(
                _MutationRecord(mutation, MutationStatus.PENDING, intents)
            )
            self._recompute_display(path)
        return mutation

    def _normalize_intents(self, intents: list[TagIntent]) -> tuple[TagIntent, ...]:
        latest_by_identity: dict[str, TagIntent] = {}
        for intent in intents:
            if intent.tag:
                latest_by_identity[intent.identity] = intent
        return tuple(latest_by_identity.values())

    def _supersede_failed_intents(
        self, path: str, newer_intents: tuple[TagIntent, ...]
    ) -> None:
        addressed = {intent.identity for intent in newer_intents}
        remaining_records: list[_MutationRecord] = []
        for record in self._records_by_path.get(path, []):
            if record.status is MutationStatus.FAILED:
                record.intents = tuple(
                    intent
                    for intent in record.intents
                    if intent.identity not in addressed
                )
            if record.intents:
                remaining_records.append(record)
        if remaining_records:
            self._records_by_path[path] = remaining_records
        else:
            self._records_by_path.pop(path, None)

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
                state = apply_tag_intents(state, record.intents)
        self._displayed_states[path] = state


def apply_tag_intents(
    state: KeywordState, intents: tuple[TagIntent, ...]
) -> KeywordState:
    """Replay TAGGER's addressed tag intent while retaining unrelated metadata."""
    keywords = state.merged
    for intent in intents:
        if intent.kind is TagIntentKind.ADD:
            if intent.identity not in {tag.casefold() for tag in keywords}:
                keywords.append(intent.tag)
        else:
            keywords = [tag for tag in keywords if tag.casefold() != intent.identity]
    keywords = dedupe_casefold(keywords)
    keywords.sort(key=str.casefold)
    return KeywordState(
        keywords,
        keywords,
        state.date_original,
        state.date_create,
        state.date_xmp_create,
        state.date_digitized,
    )
