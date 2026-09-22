"""Qt-free canonical-IPTC summary for an explicit photo selection."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from exif_tool import KeywordState
from services.keyword_limits import normalize_keyword


@dataclass(frozen=True)
class BatchTagSummary:
    """Immutable tag facts for a selected group of photos."""

    selected_count: int
    shared_tags: tuple[str, ...] = ()
    partial_tags: tuple[str, ...] = ()
    complete: bool = False


def summarize_batch_tags(
    paths: Sequence[str], states: Mapping[str, KeywordState]
) -> BatchTagSummary:
    """Summarize complete canonical-IPTC facts without inferring missing data."""
    selected_paths = tuple(paths)
    if not selected_paths:
        return BatchTagSummary(0, complete=True)

    tag_sets: list[dict[str, str]] = []
    for path in selected_paths:
        state = states.get(path)
        if state is None or not state.iptc_readable:
            return BatchTagSummary(len(selected_paths))
        tags: dict[str, str] = {}
        for raw_tag in state.iptc:
            tag = normalize_keyword(raw_tag)
            if not tag:
                continue
            identity = tag.casefold()
            previous = tags.get(identity)
            if previous is None or _display_sort_key(tag) < _display_sort_key(previous):
                tags[identity] = tag
        tag_sets.append(tags)

    occurrences: dict[str, list[str]] = {}
    for tags in tag_sets:
        for identity, tag in tags.items():
            occurrences.setdefault(identity, []).append(tag)

    shared: list[str] = []
    partial: list[str] = []
    for values in occurrences.values():
        display = min(values, key=_display_sort_key)
        if len(values) == len(selected_paths):
            shared.append(display)
        else:
            partial.append(display)
    return BatchTagSummary(
        len(selected_paths),
        tuple(sorted(shared, key=_display_sort_key)),
        tuple(sorted(partial, key=_display_sort_key)),
        complete=True,
    )


def _display_sort_key(tag: str) -> tuple[str, str]:
    return tag.casefold(), tag
