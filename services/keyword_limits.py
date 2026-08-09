"""Pure IPTC keyword-length policy shared by TAGGER's write paths."""

from __future__ import annotations

from dataclasses import dataclass
import unicodedata


IPTC_KEYWORD_MAX_UTF8_BYTES = 64


@dataclass(frozen=True)
class KeywordLengthViolation:
    """The normalized IPTC keyword that exceeds the IIM byte limit."""

    value: str
    utf8_byte_count: int

    @property
    def message(self) -> str:
        return (
            f"IPTC keyword {self.value!r} is "
            f"{self.utf8_byte_count}/{IPTC_KEYWORD_MAX_UTF8_BYTES} UTF-8 bytes"
        )


class IptcKeywordLengthError(ValueError):
    """A deterministic write-policy rejection, not an ExifTool failure."""

    def __init__(self, violation: KeywordLengthViolation):
        self.violation = violation
        super().__init__(violation.message)


def normalize_keyword(value: str) -> str:
    """Apply TAGGER's keyword normalization before comparison or validation."""
    return unicodedata.normalize("NFC", value).strip()


def keyword_length_violation(value: str) -> KeywordLengthViolation | None:
    """Return the limit violation for one value, after TAGGER normalization."""
    normalized = normalize_keyword(value)
    byte_count = len(normalized.encode("utf-8"))
    if byte_count <= IPTC_KEYWORD_MAX_UTF8_BYTES:
        return None
    return KeywordLengthViolation(normalized, byte_count)


def iptc_keyword_list_violation(values: list[str]) -> KeywordLengthViolation | None:
    """Return the first invalid IPTC keyword in display/input order."""
    for value in values:
        violation = keyword_length_violation(value)
        if violation is not None:
            return violation
    return None
