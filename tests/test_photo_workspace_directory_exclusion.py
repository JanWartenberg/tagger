"""Pure behavior tests for workspace-local directory exclusions."""

from __future__ import annotations

import unittest

from photo_workspace import PhotoWorkspace


class DirectoryExclusionTests(unittest.TestCase):
    def test_excludes_matching_ancestor_subtrees_case_insensitively(self) -> None:
        workspace = PhotoWorkspace()
        workspace.add_paths(
            [
                "C:/photos/Werkstatt/one.jpg",
                "C:/photos/elsewhere/WERKSTATT/two.jpg",
                "C:/photos/elsewhere/three.jpg",
            ]
        )

        snapshot = workspace.add_directory_exclusion("werkstatt")

        self.assertEqual(snapshot.excluded_directory_names, ("werkstatt",))
        self.assertEqual(snapshot.visible_paths, ("C:/photos/elsewhere/three.jpg",))

    def test_multiple_exclusions_are_ordered_and_additive(self) -> None:
        workspace = PhotoWorkspace()
        workspace.add_paths(
            [
                "photos/Werkstatt/one.jpg",
                "photos/alles/two.jpg",
                "photos/keep/three.jpg",
            ]
        )

        workspace.add_directory_exclusion("Werkstatt")
        snapshot = workspace.add_directory_exclusion("alles")
        duplicate = workspace.add_directory_exclusion("WERKSTATT")

        self.assertEqual(snapshot.excluded_directory_names, ("Werkstatt", "alles"))
        self.assertEqual(snapshot.visible_paths, ("photos/keep/three.jpg",))
        self.assertEqual(duplicate.excluded_directory_names, ("Werkstatt", "alles"))

    def test_clear_last_exclusion_restores_captured_selection(self) -> None:
        workspace = PhotoWorkspace()
        workspace.add_paths(["photos/keep/one.jpg", "photos/hide/two.jpg"])
        workspace.select_paths(["photos/hide/two.jpg"])

        workspace.add_directory_exclusion("hide")
        restored = workspace.clear_directory_exclusion("hide")

        self.assertEqual(restored.selected_paths, ("photos/hide/two.jpg",))
        self.assertEqual(restored.active_path, "photos/hide/two.jpg")

    def test_removing_one_of_several_exclusions_does_not_restore_until_last(
        self,
    ) -> None:
        workspace = PhotoWorkspace()
        workspace.add_paths(["photos/first/one.jpg", "photos/second/two.jpg"])
        workspace.select_paths(["photos/first/one.jpg"])
        workspace.add_directory_exclusion("first")
        workspace.add_directory_exclusion("second")

        snapshot = workspace.clear_directory_exclusion("second")

        self.assertEqual(snapshot.selected_paths, ("photos/second/two.jpg",))
        self.assertEqual(snapshot.excluded_directory_names, ("first",))

    def test_rejects_empty_and_path_like_names(self) -> None:
        workspace = PhotoWorkspace()

        with self.assertRaisesRegex(ValueError, "Folder name required"):
            workspace.add_directory_exclusion("  ")
        with self.assertRaisesRegex(ValueError, "folder name, not a path"):
            workspace.add_directory_exclusion("photos/Werkstatt")

    def test_exclusion_composes_with_filename_and_replacement_clears_it(self) -> None:
        workspace = PhotoWorkspace()
        workspace.add_paths(["photos/hide/match.jpg", "photos/keep/match.jpg"])
        workspace.set_filename_filter("match")

        filtered = workspace.add_directory_exclusion("hide")
        replacement = workspace.reload_paths(["photos/hide/replacement.jpg"])

        self.assertEqual(filtered.visible_paths, ("photos/keep/match.jpg",))
        self.assertEqual(replacement.excluded_directory_names, ())
        self.assertEqual(replacement.visible_paths, ("photos/hide/replacement.jpg",))


if __name__ == "__main__":
    unittest.main()
