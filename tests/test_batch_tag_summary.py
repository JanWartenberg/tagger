from __future__ import annotations

import unittest

from exif_tool import KeywordState
from services.batch_tag_summary import summarize_batch_tags


class BatchTagSummaryTests(unittest.TestCase):
    def test_separates_shared_and_partial_canonical_iptc_tags(self) -> None:
        summary = summarize_batch_tags(
            ("one", "two", "three"),
            {
                "one": KeywordState(["Bird", "Beach"], ["xmp-only"]),
                "two": KeywordState(["bird", "City"], []),
                "three": KeywordState(["BIRD", "Beach"], []),
            },
        )

        self.assertTrue(summary.complete)
        self.assertEqual(summary.selected_count, 3)
        self.assertEqual(summary.shared_tags, ("BIRD",))
        self.assertEqual(summary.partial_tags, ("Beach", "City"))

    def test_normalizes_unicode_and_uses_deterministic_display_spelling(self) -> None:
        summary = summarize_batch_tags(
            ("one", "two"),
            {
                "one": KeywordState([" Cafe\u0301 ", "Zoo", "zoo"], []),
                "two": KeywordState(["café", "ZOO"], []),
            },
        )

        self.assertEqual(summary.shared_tags, ("Café", "ZOO"))
        self.assertEqual(summary.partial_tags, ())

    def test_empty_tags_are_ignored_and_missing_or_unreadable_facts_are_incomplete(
        self,
    ) -> None:
        self.assertEqual(
            summarize_batch_tags(
                ("one", "two"),
                {"one": KeywordState(["", "  "], []), "two": KeywordState([], [])},
            ).shared_tags,
            (),
        )
        self.assertFalse(
            summarize_batch_tags(("one", "two"), {"one": KeywordState([], [])}).complete
        )
        self.assertFalse(
            summarize_batch_tags(
                ("one", "two"),
                {
                    "one": KeywordState([], []),
                    "two": KeywordState([], [], iptc_readable=False),
                },
            ).complete
        )


if __name__ == "__main__":
    unittest.main()
