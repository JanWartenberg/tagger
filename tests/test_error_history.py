from __future__ import annotations

import unittest
from datetime import UTC, datetime

from services.error_history import SessionError, SessionErrorHistory


class SessionErrorHistoryTests(unittest.TestCase):
    def test_records_entries_newest_first_with_timestamp_source_and_detail(
        self,
    ) -> None:
        times = iter(
            [
                datetime(2026, 8, 5, 14, 32, 8, tzinfo=UTC),
                datetime(2026, 8, 5, 14, 33, 9, tzinfo=UTC),
            ]
        )
        history = SessionErrorHistory(clock=lambda: next(times))

        history.record("Index refresh", "database is locked")
        history.record("Photo discovery", "folder is unavailable")

        self.assertEqual(
            history.entries(),
            (
                SessionError("14:33:09", "Photo discovery", "folder is unavailable"),
                SessionError("14:32:08", "Index refresh", "database is locked"),
            ),
        )

    def test_discards_the_oldest_entry_after_one_hundred_errors(self) -> None:
        history = SessionErrorHistory(
            clock=lambda: datetime(2026, 8, 5, 14, 32, 8, tzinfo=UTC)
        )

        for index in range(101):
            history.record("Index refresh", f"failure {index}")

        entries = history.entries()
        self.assertEqual(len(entries), 100)
        self.assertEqual(entries[0].detail, "failure 100")
        self.assertEqual(entries[-1].detail, "failure 1")


if __name__ == "__main__":
    unittest.main()
