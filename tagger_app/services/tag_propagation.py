"""Explicit, immutable tag-copy plans bound to assessed scan results."""

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from tagger_app.exif_tool import KeywordState
from tagger_app.services.duplicate_detection import ScanResult
from tagger_app.services.keyword_limits import iptc_keyword_list_violation
from tagger_app.services.pending_tag_mutation import MutationStatus


@dataclass(frozen=True)
class TagPropagationPlan:
    scan_id: str
    detector_id: str
    group_id: str
    source: str
    targets: tuple[str, ...]
    tags: tuple[str, ...]
    keep_backup: bool


def require_empty_target(state: KeywordState) -> None:
    """Guard the final write (including retry) against externally changed targets."""
    if not state.iptc_readable or state.iptc:
        raise ValueError("Target no longer has confirmed-empty tags")


def validate_propagation(
    plan: TagPropagationPlan,
    result: ScanResult,
    load_state: Callable[[str], KeywordState],
    status_for: Callable[[str], MutationStatus | None],
) -> dict[str, KeywordState]:
    """Revalidate an exact preview and return fresh confirmed metadata for writes."""
    if (plan.scan_id, plan.detector_id) != (result.scan_id, result.detector_id):
        raise ValueError("This copy preview belongs to a superseded scan")
    states: dict[str, KeywordState] = {}

    def refresh(path: str) -> KeywordState:
        states[path] = load_state(path)
        return states[path]

    refreshed = prepare_propagation(
        result,
        plan.group_id,
        plan.source,
        plan.targets,
        plan.keep_backup,
        refresh,
        status_for,
    )
    if refreshed != plan:
        raise ValueError("The copy preview changed; assess the candidate again")
    return states


def prepare_propagation(
    result: ScanResult,
    group_id: str,
    source: str,
    targets: Sequence[str],
    keep_backup: bool,
    load_state: Callable[[str], KeywordState],
    status_for: Callable[[str], MutationStatus | None],
) -> TagPropagationPlan:
    """Refresh file truth; reject changed assessments rather than copy stale tags."""
    group = next((group for group in result.groups if group.group_id == group_id), None)
    if group is None:
        raise ValueError("Candidate group no longer belongs to this scan")
    members = {member.path: member for member in group.members}
    selected = tuple(dict.fromkeys(targets))
    if (
        not selected
        or source in selected
        or any(path not in members for path in (source, *selected))
    ):
        raise ValueError(
            "Choose one source and empty targets within this candidate group"
        )
    for path in (source, *selected):
        member = members[path]
        state = load_state(path)
        if status_for(path) is MutationStatus.PENDING:
            raise ValueError(f"Pending tag changes must settle before copying: {path}")
        if not member.iptc_readable or not state.iptc_readable:
            raise ValueError(f"Canonical tags are unknown: {path}")
        if tuple(state.iptc) != member.iptc_tags:
            raise ValueError(f"Tags changed since assessment; scan again: {path}")
        if (path == source and not state.iptc) or (path != source and state.iptc):
            raise ValueError("Source must have tags and every target must be empty")
    tags = members[source].iptc_tags
    violation = iptc_keyword_list_violation(list(tags))
    if violation is not None:
        raise ValueError(violation.message)
    return TagPropagationPlan(
        result.scan_id,
        result.detector_id,
        group_id,
        source,
        selected,
        tags,
        keep_backup,
    )
