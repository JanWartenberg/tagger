"""Pure behavior tests for database-search workspace state."""

from __future__ import annotations

import unittest

from photo_workspace import PhotoWorkspace, PhotoWorkspaceViewMode


class DatabaseSearchTests(unittest.TestCase):
    def setUp(self) -> None:
        self.workspace = PhotoWorkspace()
        self.workspace.add_paths(["one.jpg", "two.jpg", "three.jpg"])

    def test_search_shows_only_loaded_matches_and_preserves_visible_selection(
        self,
    ) -> None:
        self.workspace.select_paths(["two.jpg"])

        snapshot = self.workspace.apply_database_search_matches(
            ["two.jpg", "outside.jpg"]
        )

        self.assertEqual(snapshot.visible_paths, ("two.jpg",))
        self.assertEqual(snapshot.selected_paths, ("two.jpg",))
        self.assertEqual(snapshot.view_mode, PhotoWorkspaceViewMode.DATABASE_SEARCH)

    def test_search_corrects_hidden_selection_to_the_first_visible_match(self) -> None:
        self.workspace.select_paths(["two.jpg"])

        snapshot = self.workspace.apply_database_search_matches(["three.jpg"])

        self.assertEqual(snapshot.visible_paths, ("three.jpg",))
        self.assertEqual(snapshot.selected_paths, ("three.jpg",))
        self.assertEqual(snapshot.active_path, "three.jpg")

    def test_clear_search_restores_all_paths_and_current_selection(self) -> None:
        self.workspace.select_paths(["two.jpg"])
        self.workspace.apply_database_search_matches(["two.jpg"])

        snapshot = self.workspace.clear_database_search()

        self.assertEqual(snapshot.visible_paths, ("one.jpg", "two.jpg", "three.jpg"))
        self.assertEqual(snapshot.selected_paths, ("two.jpg",))
        self.assertEqual(snapshot.view_mode, PhotoWorkspaceViewMode.NORMAL)

    def test_search_invalidates_inflight_iptc_filter_work(self) -> None:
        self.workspace.start_iptc_empty_filter(1, 1)
        batch = self.workspace.next_iptc_empty_filter_batch()
        search_snapshot = self.workspace.apply_database_search_matches(["two.jpg"])

        snapshot = self.workspace.accept_iptc_empty_filter_batch(
            batch.operation_id, ["one.jpg"]
        )

        self.assertEqual(snapshot, search_snapshot)
        self.assertEqual(snapshot.visible_paths, ("two.jpg",))
        self.assertEqual(snapshot.view_mode, PhotoWorkspaceViewMode.DATABASE_SEARCH)

    def test_starting_iptc_filter_leaves_database_search_view(self) -> None:
        self.workspace.apply_database_search_matches(["two.jpg"])

        snapshot = self.workspace.start_iptc_empty_filter(1, 1)

        self.assertEqual(snapshot.view_mode, PhotoWorkspaceViewMode.IPTC_EMPTY)


if __name__ == "__main__":
    unittest.main()
