"""Pure behavior tests for the workspace-local filename filter."""

from __future__ import annotations

import unittest

from photo_workspace import PhotoWorkspace, PhotoWorkspaceViewMode


class FilenameFilterTests(unittest.TestCase):
    def test_filters_complete_basenames_with_trimmed_casefolded_substrings(
        self,
    ) -> None:
        workspace = PhotoWorkspace()
        workspace.add_paths(
            [
                "photos/DSC_001.JPG",
                "photos/holiday-dsc-notes.txt",
                "DSC-directory/other.jpg",
            ]
        )

        snapshot = workspace.set_filename_filter("  dSc  ")

        self.assertEqual(
            snapshot.visible_paths,
            ("photos/DSC_001.JPG", "photos/holiday-dsc-notes.txt"),
        )
        self.assertEqual(snapshot.filename_filter_query, "dSc")
        self.assertFalse(snapshot.filename_filter_case_sensitive)

    def test_case_sensitive_matching_normalizes_unicode_but_preserves_case(
        self,
    ) -> None:
        workspace = PhotoWorkspace()
        workspace.add_paths(["photos/Café.JPG", "photos/café.jpg"])

        snapshot = workspace.set_filename_filter("Cafe\u0301.JPG", case_sensitive=True)

        self.assertEqual(snapshot.visible_paths, ("photos/Café.JPG",))

    def test_filename_condition_composes_with_search_and_iptc_empty_sources(
        self,
    ) -> None:
        workspace = PhotoWorkspace()
        workspace.add_paths(["plain.jpg", "needle.jpg"])

        workspace.set_filename_filter("needle")
        searched = workspace.apply_database_search_matches(
            ["plain-result.jpg", "needle-result.jpg"]
        )
        started = workspace.start_indexed_iptc_empty_filter()
        filtered = workspace.accept_indexed_iptc_empty_filter(
            started.filter_operation_id or -1,
            ["plain-result.jpg", "needle-result.jpg"],
        )
        restored_search = workspace.clear_iptc_empty_filter()
        restored_folder = workspace.clear_database_search()

        self.assertEqual(searched.visible_paths, ("needle-result.jpg",))
        self.assertEqual(filtered.visible_paths, ("needle-result.jpg",))
        self.assertEqual(restored_search.visible_paths, ("needle-result.jpg",))
        self.assertEqual(restored_folder.visible_paths, ("needle.jpg",))

    def test_workspace_count_keeps_the_folder_size_during_an_indexed_search(
        self,
    ) -> None:
        workspace = PhotoWorkspace()
        workspace.add_paths(["first.jpg", "second.jpg"])

        workspace.apply_database_search_matches(["second.jpg"])

        self.assertEqual(workspace.workspace_path_count, 2)

    def test_search_started_after_iptc_empty_keeps_both_conditions_active(self) -> None:
        workspace = PhotoWorkspace()
        workspace.add_paths(["plain.jpg", "iptc.jpg", "other.jpg"])
        started = workspace.start_indexed_iptc_empty_filter()
        workspace.accept_indexed_iptc_empty_filter(
            started.filter_operation_id or -1, ["iptc.jpg", "other.jpg"]
        )

        searched = workspace.apply_database_search_matches(["plain.jpg", "iptc.jpg"])
        restored = workspace.clear_database_search()

        self.assertTrue(searched.has_database_search)
        self.assertEqual(searched.view_mode, PhotoWorkspaceViewMode.IPTC_EMPTY)
        self.assertEqual(searched.visible_paths, ("iptc.jpg",))
        self.assertEqual(restored.visible_paths, ("iptc.jpg", "other.jpg"))

    def test_incoming_paths_obey_an_active_filename_condition(self) -> None:
        workspace = PhotoWorkspace()
        workspace.add_paths(["match.jpg"])
        workspace.set_filename_filter("match")

        snapshot = workspace.add_paths(["plain.jpg", "another-match.jpg"])

        self.assertEqual(snapshot.visible_paths, ("match.jpg", "another-match.jpg"))

    def test_workspace_replacement_clears_the_filename_condition(self) -> None:
        workspace = PhotoWorkspace()
        workspace.add_paths(["match.jpg"])
        workspace.set_filename_filter("match", case_sensitive=True)

        snapshot = workspace.reload_paths(["replacement.jpg"])

        self.assertIsNone(snapshot.filename_filter_query)
        self.assertFalse(snapshot.filename_filter_case_sensitive)
        self.assertEqual(snapshot.visible_paths, ("replacement.jpg",))

    def test_clear_all_filters_restores_the_folder_view(self) -> None:
        workspace = PhotoWorkspace()
        workspace.add_paths(["first.jpg", "second.jpg"])
        workspace.set_filename_filter("second")
        workspace.apply_database_search_matches(["second.jpg"])
        started = workspace.start_indexed_iptc_empty_filter()
        workspace.accept_indexed_iptc_empty_filter(
            started.filter_operation_id or -1, ["second.jpg"]
        )

        snapshot = workspace.clear_all_filters()

        self.assertEqual(snapshot.paths, ("first.jpg", "second.jpg"))
        self.assertEqual(snapshot.visible_paths, ("first.jpg", "second.jpg"))
        self.assertIsNone(snapshot.filename_filter_query)

    def test_clearing_restores_the_pre_filter_selection(self) -> None:
        workspace = PhotoWorkspace()
        workspace.add_paths(["keep.jpg", "match.jpg"])
        workspace.select_paths(["keep.jpg"])

        workspace.set_filename_filter("match")
        restored = workspace.clear_filename_filter()

        self.assertEqual(restored.visible_paths, ("keep.jpg", "match.jpg"))
        self.assertEqual(restored.selected_paths, ("keep.jpg",))
        self.assertEqual(restored.active_path, "keep.jpg")


if __name__ == "__main__":
    unittest.main()
