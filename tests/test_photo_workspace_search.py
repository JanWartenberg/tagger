"""Pure behavior tests for database-search workspace state."""

from __future__ import annotations

import unittest

from photo_workspace import PhotoWorkspace, PhotoWorkspaceViewMode


class DatabaseSearchTests(unittest.TestCase):
    def setUp(self) -> None:
        self.workspace = PhotoWorkspace()
        self.workspace.add_paths(["one.jpg", "two.jpg", "three.jpg"])

    def test_search_shows_external_indexed_matches_and_restores_folder_state(
        self,
    ) -> None:
        self.workspace.select_paths(["two.jpg"])

        snapshot = self.workspace.apply_database_search_matches(
            ["two.jpg", "outside.jpg"]
        )

        self.assertEqual(snapshot.paths, ("two.jpg", "outside.jpg"))
        self.assertEqual(snapshot.visible_paths, ("two.jpg", "outside.jpg"))
        self.assertEqual(snapshot.selected_paths, ("two.jpg",))
        self.assertEqual(snapshot.view_mode, PhotoWorkspaceViewMode.DATABASE_SEARCH)

        restored = self.workspace.clear_database_search()

        self.assertEqual(restored.paths, ("one.jpg", "two.jpg", "three.jpg"))
        self.assertEqual(restored.selected_paths, ("two.jpg",))
        self.assertEqual(restored.view_mode, PhotoWorkspaceViewMode.NORMAL)

    def test_search_corrects_hidden_selection_to_the_first_visible_match(self) -> None:
        self.workspace.select_paths(["two.jpg"])

        snapshot = self.workspace.apply_database_search_matches(["three.jpg"])

        self.assertEqual(snapshot.visible_paths, ("three.jpg",))
        self.assertEqual(snapshot.selected_paths, ("three.jpg",))
        self.assertEqual(snapshot.active_path, "three.jpg")

    def test_replaced_search_retains_the_original_folder_restoration_state(
        self,
    ) -> None:
        self.workspace.select_paths(["two.jpg"])
        self.workspace.apply_database_search_matches(["outside.jpg"])
        self.workspace.select_paths(["outside.jpg"])

        snapshot = self.workspace.apply_database_search_matches(["three.jpg"])

        self.assertEqual(snapshot.paths, ("three.jpg",))
        self.assertEqual(snapshot.selected_paths, ("three.jpg",))

        restored = self.workspace.clear_database_search()

        self.assertEqual(restored.paths, ("one.jpg", "two.jpg", "three.jpg"))
        self.assertEqual(restored.selected_paths, ("two.jpg",))

    def test_empty_search_result_is_restorable(self) -> None:
        self.workspace.select_paths(["three.jpg"])

        snapshot = self.workspace.apply_database_search_matches([])

        self.assertEqual(snapshot.paths, ())
        self.assertEqual(snapshot.selected_paths, ())
        self.assertEqual(snapshot.view_mode, PhotoWorkspaceViewMode.DATABASE_SEARCH)

        restored = self.workspace.clear_database_search()

        self.assertEqual(restored.paths, ("one.jpg", "two.jpg", "three.jpg"))
        self.assertEqual(restored.selected_paths, ("three.jpg",))

    def test_search_invalidates_inflight_iptc_filter_work(self) -> None:
        self.workspace.start_iptc_empty_filter(1, 1)
        batch = self.workspace.next_iptc_empty_filter_batch()
        search_snapshot = self.workspace.apply_database_search_matches(["outside.jpg"])

        snapshot = self.workspace.accept_iptc_empty_filter_batch(
            batch.operation_id, ["one.jpg"]
        )

        self.assertEqual(snapshot, search_snapshot)
        self.assertEqual(snapshot.visible_paths, ("outside.jpg",))
        self.assertEqual(snapshot.view_mode, PhotoWorkspaceViewMode.DATABASE_SEARCH)

    def test_starting_iptc_filter_keeps_database_search_visible_while_scanning(
        self,
    ) -> None:
        self.workspace.apply_database_search_matches(["two.jpg"])

        snapshot = self.workspace.start_iptc_empty_filter(1, 1)

        self.assertEqual(snapshot.view_mode, PhotoWorkspaceViewMode.DATABASE_SEARCH)
        self.assertEqual(snapshot.visible_paths, ("two.jpg",))
        self.assertEqual(snapshot.selected_paths, ("two.jpg",))
        self.assertEqual(snapshot.active_path, "two.jpg")
        self.assertIsNotNone(snapshot.filter_operation_id)


if __name__ == "__main__":
    unittest.main()
