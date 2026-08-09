from __future__ import annotations

import unittest

from exif_tool import KeywordState
from services.tag_mutation import TagMutationService


class TagMutationServiceTests(unittest.TestCase):
    def test_ordinary_mutation_preserves_an_empty_xmp_field(self) -> None:
        path = "C:/photos/one.jpg"
        exif = FakeExifTool({path: KeywordState(["before"], [])}, failed_paths=set())

        result = TagMutationService(exif).add_tag(
            [path], "added", keep_backup=False, load_state=exif.read_keywords
        )

        self.assertEqual(
            result.updated_states[path], KeywordState(["added", "before"], [])
        )
        self.assertEqual(
            exif.states_by_path[path], KeywordState(["added", "before"], [])
        )

    def test_resolve_writes_field_specific_choices_in_one_operation(self) -> None:
        path = "C:/photos/one.jpg"
        exif = FakeExifTool({path: KeywordState(["iptc"], ["xmp"])}, failed_paths=set())
        chosen = KeywordState(["iptc", "xmp"], ["xmp"])

        result = TagMutationService(exif).resolve_keyword_fields(
            [path], {path: chosen}, keep_backup=False, load_state=exif.read_keywords
        )

        self.assertEqual(result.updated_states[path], chosen)
        self.assertEqual(exif.write_calls, [(path, ["iptc", "xmp"], ["xmp"])])

    def test_resolve_retries_a_failed_field_pair_at_most_three_times(self) -> None:
        path = "C:/photos/one.jpg"
        exif = FakeExifTool(
            {path: KeywordState(["iptc"], ["xmp"])}, failed_paths={path}
        )
        chosen = KeywordState(["iptc"], ["iptc"])

        result = TagMutationService(exif).resolve_keyword_fields(
            [path], {path: chosen}, keep_backup=False, load_state=exif.read_keywords
        )

        self.assertEqual(result.failed_paths, {path: "simulated write failure"})
        self.assertEqual(len(exif.write_calls), 3)

    def test_rejects_an_invalid_final_iptc_target_without_calling_exiftool(
        self,
    ) -> None:
        path = "C:/photos/one.jpg"
        exif = FakeExifTool({path: KeywordState(["before"], [])}, failed_paths=set())

        result = TagMutationService(exif).add_tag(
            [path], "x" * 65, keep_backup=False, load_state=exif.read_keywords
        )

        self.assertEqual(exif.write_calls, [])
        self.assertIn("65/64 UTF-8 bytes", result.failed_paths[path])

    def test_resolve_rejects_an_invalid_target_without_retries(self) -> None:
        path = "C:/photos/one.jpg"
        exif = FakeExifTool({path: KeywordState([], ["x" * 65])}, failed_paths=set())

        result = TagMutationService(exif).resolve_keyword_fields(
            [path],
            {path: KeywordState(["x" * 65], ["x" * 65])},
            keep_backup=False,
            load_state=exif.read_keywords,
        )

        self.assertEqual(exif.write_calls, [])
        self.assertEqual(result.attempts_by_path[path], 0)

    def test_partial_write_failure_returns_confirmed_and_failed_paths(self) -> None:
        first = "C:/photos/one.jpg"
        second = "C:/photos/two.jpg"
        exif = FakeExifTool(
            {
                first: KeywordState(["one-before"], ["one-before"]),
                second: KeywordState(["two-before"], ["two-before"]),
            },
            failed_paths={second},
        )

        result = TagMutationService(exif).add_tag(
            [first, second], "added", keep_backup=False, load_state=exif.read_keywords
        )

        self.assertEqual(
            result.updated_states,
            {first: KeywordState(["added", "one-before"], ["added", "one-before"])},
        )
        self.assertEqual(result.emptiness_by_path, {first: False})
        self.assertEqual(result.failed_paths, {second: "simulated write failure"})
        self.assertEqual(result.processed_count, 2)
        self.assertEqual(result.changed_count, 1)


class FakeExifTool:
    def __init__(
        self, states_by_path: dict[str, KeywordState], failed_paths: set[str]
    ) -> None:
        self.states_by_path = states_by_path
        self.failed_paths = failed_paths
        self.write_calls: list[tuple[str, list[str], list[str]]] = []

    def read_keywords(self, path: str) -> KeywordState:
        return self.states_by_path[path]

    def write_keyword_fields(
        self,
        paths: list[str],
        iptc: list[str],
        xmp: list[str],
        keep_backup: bool,
    ) -> None:
        del keep_backup
        path = paths[0]
        self.write_calls.append((path, list(iptc), list(xmp)))
        if path in self.failed_paths:
            raise RuntimeError("simulated write failure")
        self.states_by_path[path] = KeywordState(iptc, xmp)


if __name__ == "__main__":
    unittest.main()
