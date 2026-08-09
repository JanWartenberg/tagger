import unittest

from services.keyword_limits import (
    IPTC_KEYWORD_MAX_UTF8_BYTES,
    iptc_keyword_list_violation,
    keyword_length_violation,
)


class KeywordLengthPolicyTests(unittest.TestCase):
    def test_accepts_64_utf8_bytes_and_rejects_65(self) -> None:
        self.assertIsNone(keyword_length_violation("a" * 64))

        violation = keyword_length_violation("a" * 65)

        self.assertIsNotNone(violation)
        assert violation is not None
        self.assertEqual(violation.utf8_byte_count, 65)
        self.assertEqual(IPTC_KEYWORD_MAX_UTF8_BYTES, 64)

    def test_counts_normalized_multibyte_utf8_and_trims_outer_whitespace(self) -> None:
        self.assertIsNone(keyword_length_violation(" " + "\u00e9" * 32 + " "))

        violation = keyword_length_violation("e\u0301" * 33)

        self.assertIsNotNone(violation)
        assert violation is not None
        self.assertEqual(violation.value, "\u00e9" * 33)
        self.assertEqual(violation.utf8_byte_count, 66)

    def test_returns_first_invalid_keyword_from_a_list(self) -> None:
        violation = iptc_keyword_list_violation(["valid", "x" * 65, "y" * 66])

        self.assertIsNotNone(violation)
        assert violation is not None
        self.assertEqual(violation.value, "x" * 65)


if __name__ == "__main__":
    unittest.main()
