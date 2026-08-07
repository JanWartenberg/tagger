from dataclasses import dataclass, replace
from enum import Enum

from exif_tool import KeywordState
from utils import dedupe_casefold


class MutationStatus(str, Enum):
    PENDING = "pending"
    FAILED = "failed"


class TagIntentKind(str, Enum):
    ADD = "add"
    REMOVE = "remove"
    REPLACE_FIELDS = "replace-fields"


@dataclass(frozen=True)
class TagIntent:
    """One requested canonical-tag change or explicit keyword-field replacement."""

    kind: TagIntentKind
    tag: str = ""
    target_state: KeywordState | None = None
    attempts: int = 0

    @classmethod
    def add(cls, tag: str) -> "TagIntent":
        return cls(TagIntentKind.ADD, tag.strip())

    @classmethod
    def remove(cls, tag: str) -> "TagIntent":
        return cls(TagIntentKind.REMOVE, tag.strip())

    @classmethod
    def replace_fields(cls, target_state: KeywordState) -> "TagIntent":
        return cls(TagIntentKind.REPLACE_FIELDS, target_state=target_state)

    @property
    def identity(self) -> str:
        if self.kind is TagIntentKind.REPLACE_FIELDS:
            return "__keyword-fields__"
        return self.tag.casefold()

    @property
    def retryable(self) -> bool:
        return self.kind is not TagIntentKind.REPLACE_FIELDS or self.attempts < 3


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
        self,
        mutation: PendingTagMutation,
        paths: list[str] | None = None,
        attempts_by_path: dict[str, int] | None = None,
    ) -> dict[str, KeywordState]:
        displayed: dict[str, KeywordState] = {}
        affected_paths = paths if paths is not None else list(mutation.intents_by_path)
        for path in affected_paths:
            for record in self._records_by_path.get(path, []):
                if record.mutation == mutation:
                    record.status = MutationStatus.FAILED
                    attempts = (attempts_by_path or {}).get(path, 0)
                    if attempts:
                        record.intents = tuple(
                            replace(intent, attempts=intent.attempts + attempts)
                            if intent.kind is TagIntentKind.REPLACE_FIELDS
                            else intent
                            for intent in record.intents
                        )
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
            records = self._records_by_path.get(path, [])
            retryable = [
                intent
                for record in records
                if record.status is MutationStatus.FAILED
                for intent in record.intents
                if intent.retryable
            ]
            if not retryable:
                continue
            intents_by_path[path] = retryable
            retained: list[_MutationRecord] = []
            for record in records:
                if record.status is not MutationStatus.FAILED:
                    retained.append(record)
                    continue
                record.intents = tuple(
                    intent for intent in record.intents if not intent.retryable
                )
                if record.intents:
                    retained.append(record)
            if retained:
                self._records_by_path[path] = retained
            else:
                self._records_by_path.pop(path, None)
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
            if intent.kind is TagIntentKind.REPLACE_FIELDS or intent.tag:
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
    """Replay requested canonical-tag intent while retaining field-specific facts."""
    current = state
    preserve_empty_xmp = not current.xmp
    for intent in intents:
        if intent.kind is TagIntentKind.REPLACE_FIELDS:
            if intent.target_state is None:
                continue
            current = intent.target_state
            preserve_empty_xmp = not current.xmp
            continue
        keywords = list(current.iptc)
        if intent.kind is TagIntentKind.ADD:
            if intent.identity not in {tag.casefold() for tag in keywords}:
                keywords.append(intent.tag)
        else:
            keywords = [tag for tag in keywords if tag.casefold() != intent.identity]
        keywords = dedupe_casefold(keywords)
        keywords.sort(key=str.casefold)
        # An intentionally empty XMP field remains empty during routine edits.
        xmp = [] if preserve_empty_xmp else keywords
        current = KeywordState(
            keywords,
            xmp,
            current.date_original,
            current.date_create,
            current.date_xmp_create,
            current.date_digitized,
            current.iptc_readable,
            current.xmp_readable,
        )
    return current
