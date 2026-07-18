from __future__ import annotations

import unittest

from exif_tool import KeywordState
from services.tag_mutation import TagMutationService


class TagMutationServiceTests(unittest.TestCase):
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

    def read_keywords(self, path: str) -> KeywordState:
        return self.states_by_path[path]

    def write_keywords(
        self, paths: list[str], keywords: list[str], keep_backup: bool
    ) -> None:
        del keep_backup
        path = paths[0]
        if path in self.failed_paths:
            raise RuntimeError("simulated write failure")
        self.states_by_path[path] = KeywordState(keywords, keywords)


if __name__ == "__main__":
    unittest.main()
