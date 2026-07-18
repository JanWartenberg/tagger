"""Pure behavior tests for the PhotoWorkspace interface."""

from __future__ import annotations

import unittest

from photo_workspace import PhotoWorkspace


class PhotoWorkspaceTests(unittest.TestCase):
    def test_add_preserves_normalized_path_order_and_ignores_duplicates(self) -> None:
        workspace = PhotoWorkspace()

        snapshot = workspace.add_paths(["photos/one.jpg", "photos/two.jpg", "photos/one.jpg"])

        self.assertEqual(snapshot.paths, ("photos/one.jpg", "photos/two.jpg"))
        self.assertEqual(snapshot.visible_paths, ("photos/one.jpg", "photos/two.jpg"))
        self.assertEqual(snapshot.selected_paths, ("photos/one.jpg",))
        self.assertEqual(snapshot.active_path, "photos/one.jpg")

    def test_selection_is_ordered_by_display_order_and_active_path_is_first(self) -> None:
        workspace = PhotoWorkspace()
        workspace.add_paths(["one.jpg", "two.jpg", "three.jpg"])

        snapshot = workspace.select_paths(["three.jpg", "one.jpg"])

        self.assertEqual(snapshot.selected_paths, ("one.jpg", "three.jpg"))
        self.assertEqual(snapshot.active_path, "one.jpg")

    def test_reload_replaces_membership_and_selects_first_path(self) -> None:
        workspace = PhotoWorkspace()
        workspace.add_paths(["one.jpg", "two.jpg"])
        workspace.select_paths(["two.jpg"])

        snapshot = workspace.reload_paths(["three.jpg", "three.jpg", "four.jpg"])

        self.assertEqual(snapshot.paths, ("three.jpg", "four.jpg"))
        self.assertEqual(snapshot.selected_paths, ("three.jpg",))
        self.assertEqual(snapshot.active_path, "three.jpg")

    def test_clearing_user_selection_does_not_reactivate_the_first_photo(self) -> None:
        workspace = PhotoWorkspace()
        workspace.add_paths(["one.jpg", "two.jpg"])
        workspace.select_paths(["two.jpg"])

        snapshot = workspace.select_paths([])

        self.assertEqual(snapshot.selected_paths, ())
        self.assertIsNone(snapshot.active_path)

    def test_hiding_active_photo_selects_first_remaining_visible_photo(self) -> None:
        workspace = PhotoWorkspace()
        workspace.add_paths(["one.jpg", "two.jpg", "three.jpg"])
        workspace.select_paths(["two.jpg", "three.jpg"])

        snapshot = workspace.set_visible_paths(["one.jpg", "three.jpg"])

        self.assertEqual(snapshot.visible_paths, ("one.jpg", "three.jpg"))
        self.assertEqual(snapshot.selected_paths, ("three.jpg",))
        self.assertEqual(snapshot.active_path, "three.jpg")

    def test_hiding_every_photo_clears_selection_and_active_photo(self) -> None:
        workspace = PhotoWorkspace()
        workspace.add_paths(["one.jpg", "two.jpg"])

        snapshot = workspace.set_visible_paths([])

        self.assertEqual(snapshot.visible_paths, ())
        self.assertEqual(snapshot.selected_paths, ())
        self.assertIsNone(snapshot.active_path)


if __name__ == "__main__":
    unittest.main()
