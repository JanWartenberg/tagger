"""Session-scoped history of user-visible operational failures."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class SessionError:
    """One timestamped operational failure shown to the user."""

    timestamp: str
    source: str
    detail: str


class SessionErrorHistory:
    """Keep the newest bounded set of errors for one application session."""

    max_entries = 100

    def __init__(self, *, clock: Callable[[], datetime] = datetime.now) -> None:
        self._clock = clock
        self._entries: list[SessionError] = []

    def record(self, source: str, detail: str) -> None:
        self._entries.insert(
            0,
            SessionError(
                timestamp=self._clock().strftime("%H:%M:%S"),
                source=source,
                detail=detail,
            ),
        )
        del self._entries[self.max_entries :]

    def entries(self) -> tuple[SessionError, ...]:
        """Return entries in reverse chronological order."""
        return tuple(self._entries)
