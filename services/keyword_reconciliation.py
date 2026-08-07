"""Classify IPTC/XMP keyword facts for the single-photo Resolve workflow."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import unicodedata

from exif_tool import KeywordState


class MismatchKind(str, Enum):
    S1 = "both-empty"
    S2 = "iptc-empty-xmp-nonempty"
    S3 = "iptc-nonempty-xmp-empty"
    S4 = "equal-nonempty"
    S5 = "iptc-subset-xmp"
    S6 = "xmp-subset-iptc"
    S7 = "overlap"
    S8 = "disjoint"
    UNREADABLE_IPTC = "unreadable-iptc"
    UNREADABLE_XMP = "unreadable-xmp"
    UNREADABLE_BOTH = "unreadable-both"


_RESOLVABLE_KINDS = {
    MismatchKind.S2,
    MismatchKind.S5,
    MismatchKind.S6,
    MismatchKind.S7,
    MismatchKind.S8,
    MismatchKind.UNREADABLE_IPTC,
    MismatchKind.UNREADABLE_XMP,
    MismatchKind.UNREADABLE_BOTH,
}


def normalize_keywords(values: list[str]) -> tuple[str, ...]:
    """Apply TAGGER's field-local comparison and display normalization."""
    result: list[str] = []
    identities: set[str] = set()
    for value in values:
        normalized = unicodedata.normalize("NFC", value).strip()
        if not normalized:
            continue
        identity = normalized.casefold()
        if identity in identities:
            continue
        identities.add(identity)
        result.append(normalized)
    return tuple(result)


@dataclass(frozen=True)
class KeywordReconciliation:
    """Normalized keyword facts and their policy classification."""

    kind: MismatchKind
    iptc: tuple[str, ...]
    xmp: tuple[str, ...]

    @property
    def requires_resolution(self) -> bool:
        return self.kind in _RESOLVABLE_KINDS

    @property
    def can_copy(self) -> bool:
        return self.kind not in {
            MismatchKind.UNREADABLE_IPTC,
            MismatchKind.UNREADABLE_XMP,
            MismatchKind.UNREADABLE_BOTH,
        }

    @property
    def current_tags(self) -> tuple[str, ...]:
        """IPTC is TAGGER's canonical field and the sole detail-pane truth."""
        return self.iptc


def aligned_keyword_rows(
    iptc: tuple[str, ...], xmp: tuple[str, ...]
) -> tuple[tuple[str | None, str | None], ...]:
    """Align equal keyword identities while keeping field-local order stable."""
    xmp_by_identity = {keyword.casefold(): keyword for keyword in xmp}
    matched = set[str]()
    rows: list[tuple[str | None, str | None]] = []
    for keyword in iptc:
        identity = keyword.casefold()
        xmp_keyword = xmp_by_identity.get(identity)
        if xmp_keyword is not None:
            matched.add(identity)
        rows.append((keyword, xmp_keyword))
    rows.extend((None, keyword) for keyword in xmp if keyword.casefold() not in matched)
    return tuple(rows)


def reconcile_keywords(state: KeywordState) -> KeywordReconciliation:
    iptc = normalize_keywords(state.iptc)
    xmp = normalize_keywords(state.xmp)
    if not state.iptc_readable and not state.xmp_readable:
        kind = MismatchKind.UNREADABLE_BOTH
    elif not state.iptc_readable:
        kind = MismatchKind.UNREADABLE_IPTC
    elif not state.xmp_readable:
        kind = MismatchKind.UNREADABLE_XMP
    else:
        iptc_identities = {keyword.casefold() for keyword in iptc}
        xmp_identities = {keyword.casefold() for keyword in xmp}
        if not iptc_identities and not xmp_identities:
            kind = MismatchKind.S1
        elif not iptc_identities:
            kind = MismatchKind.S2
        elif not xmp_identities:
            kind = MismatchKind.S3
        elif iptc_identities == xmp_identities:
            kind = MismatchKind.S4
        elif iptc_identities < xmp_identities:
            kind = MismatchKind.S5
        elif xmp_identities < iptc_identities:
            kind = MismatchKind.S6
        elif iptc_identities & xmp_identities:
            kind = MismatchKind.S7
        else:
            kind = MismatchKind.S8
    return KeywordReconciliation(kind, iptc, xmp)
