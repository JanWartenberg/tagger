from __future__ import annotations

import unittest

from exif_tool import KeywordState
from services.keyword_reconciliation import (
    MismatchKind,
    aligned_keyword_rows,
    reconcile_keywords,
)


class KeywordReconciliationTests(unittest.TestCase):
    def test_classifies_all_readable_keyword_relationships(self) -> None:
        cases = {
            MismatchKind.S1: ([], []),
            MismatchKind.S2: ([], ["beach"]),
            MismatchKind.S3: (["beach"], []),
            MismatchKind.S4: (["beach", "bird"], ["bird", "beach"]),
            MismatchKind.S5: (["beach"], ["beach", "bird"]),
            MismatchKind.S6: (["beach", "bird"], ["beach"]),
            MismatchKind.S7: (["beach", "bird"], ["beach", "sunset"]),
            MismatchKind.S8: (["beach"], ["mountain"]),
        }

        for expected, (iptc, xmp) in cases.items():
            with self.subTest(expected=expected):
                result = reconcile_keywords(KeywordState(iptc, xmp))
                self.assertEqual(result.kind, expected)
                self.assertEqual(
                    result.requires_resolution,
                    expected
                    in {
                        MismatchKind.S2,
                        MismatchKind.S5,
                        MismatchKind.S6,
                        MismatchKind.S7,
                        MismatchKind.S8,
                    },
                )

    def test_normalizes_in_place_for_comparison_and_display(self) -> None:
        result = reconcile_keywords(
            KeywordState([" beach ", "BEACH", "Cafe\u0301", ""], ["café", "beach"])
        )

        self.assertEqual(result.kind, MismatchKind.S4)
        self.assertEqual(result.iptc, ("beach", "Café"))
        self.assertEqual(result.xmp, ("café", "beach"))
        self.assertEqual(result.current_tags, ("beach", "Café"))

    def test_aligns_matching_keywords_and_leaves_disjoint_cells_empty(self) -> None:
        rows = aligned_keyword_rows(
            ("foo", "bar"),
            ("bar", "baz"),
        )

        self.assertEqual(rows, (("foo", None), ("bar", "bar"), (None, "baz")))

    def test_unreadable_field_needs_recovery_without_a_derived_overwrite(self) -> None:
        result = reconcile_keywords(KeywordState([], ["beach"], iptc_readable=False))

        self.assertEqual(result.kind, MismatchKind.UNREADABLE_IPTC)
        self.assertTrue(result.requires_resolution)
        self.assertEqual(result.current_tags, ())
        self.assertFalse(result.can_copy)


if __name__ == "__main__":
    unittest.main()
