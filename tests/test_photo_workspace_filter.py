from __future__ import annotations

import unittest

from photo_workspace import PhotoWorkspace, PhotoWorkspaceViewMode


class IptcEmptyFilterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.workspace = PhotoWorkspace()
        self.workspace.add_paths(["one.jpg", "two.jpg", "three.jpg"])

    def test_stale_batch_does_not_change_new_filter(self) -> None:
        self.workspace.start_iptc_empty_filter(1, 1)
        stale = self.workspace.next_iptc_empty_filter_batch()
        self.workspace.start_iptc_empty_filter(1, 1)

        snapshot = self.workspace.accept_iptc_empty_filter_batch(
            stale.operation_id, ["one.jpg"]
        )

        self.assertEqual(snapshot.visible_paths, ("one.jpg", "two.jpg", "three.jpg"))
        self.assertEqual(snapshot.filter_processed, 0)

    def test_failed_filter_restores_last_successful_view(self) -> None:
        self.workspace.apply_database_search_matches(["two.jpg"])
        self.workspace.start_iptc_empty_filter(1, 1)
        batch = self.workspace.next_iptc_empty_filter_batch()

        snapshot = self.workspace.fail_iptc_empty_filter_batch(batch.operation_id)

        self.assertEqual(snapshot.view_mode, PhotoWorkspaceViewMode.DATABASE_SEARCH)
        self.assertEqual(snapshot.visible_paths, ("two.jpg",))
        self.assertEqual(snapshot.selected_paths, ("two.jpg",))

    def test_failed_later_batch_discards_partial_results_and_restores_source_view(
        self,
    ) -> None:
        self.workspace.select_paths(["two.jpg"])
        self.workspace.start_iptc_empty_filter(1, 1)
        first_batch = self.workspace.next_iptc_empty_filter_batch()
        pending = self.workspace.accept_iptc_empty_filter_batch(
            first_batch.operation_id, ["one.jpg"]
        )
        failing_batch = self.workspace.next_iptc_empty_filter_batch()

        snapshot = self.workspace.fail_iptc_empty_filter_batch(
            failing_batch.operation_id
        )

        self.assertEqual(pending.visible_paths, ("one.jpg", "two.jpg", "three.jpg"))
        self.assertEqual(snapshot.view_mode, PhotoWorkspaceViewMode.NORMAL)
        self.assertEqual(snapshot.visible_paths, ("one.jpg", "two.jpg", "three.jpg"))
        self.assertEqual(snapshot.selected_paths, ("two.jpg",))

    def test_filter_applies_completed_results_atomically_and_selects_first_match(
        self,
    ) -> None:
        self.workspace.select_paths(["two.jpg"])
        self.workspace.start_iptc_empty_filter(1, 1)

        first = self.workspace.next_iptc_empty_filter_batch()
        pending = self.workspace.accept_iptc_empty_filter_batch(
            first.operation_id, ["one.jpg"]
        )
        second = self.workspace.next_iptc_empty_filter_batch()
        pending = self.workspace.accept_iptc_empty_filter_batch(second.operation_id, [])
        third = self.workspace.next_iptc_empty_filter_batch()
        completed = self.workspace.accept_iptc_empty_filter_batch(
            third.operation_id, ["three.jpg"]
        )

        self.assertEqual(pending.view_mode, PhotoWorkspaceViewMode.NORMAL)
        self.assertEqual(pending.visible_paths, ("one.jpg", "two.jpg", "three.jpg"))
        self.assertEqual(pending.selected_paths, ("two.jpg",))
        self.assertEqual(completed.view_mode, PhotoWorkspaceViewMode.IPTC_EMPTY)
        self.assertEqual(completed.visible_paths, ("one.jpg", "three.jpg"))
        self.assertEqual(completed.selected_paths, ("one.jpg",))
        self.assertEqual(completed.active_path, "one.jpg")

    def test_empty_final_result_hides_all_photos(self) -> None:
        self.workspace.start_iptc_empty_filter(3, 3)
        batch = self.workspace.next_iptc_empty_filter_batch()

        snapshot = self.workspace.accept_iptc_empty_filter_batch(batch.operation_id, [])

        self.assertEqual(snapshot.view_mode, PhotoWorkspaceViewMode.IPTC_EMPTY)
        self.assertEqual(snapshot.visible_paths, ())
        self.assertEqual(snapshot.selected_paths, ())

    def test_restarting_after_failure_uses_a_fresh_filter_operation(self) -> None:
        self.workspace.start_iptc_empty_filter(1, 1)
        failed_batch = self.workspace.next_iptc_empty_filter_batch()
        self.workspace.fail_iptc_empty_filter_batch(failed_batch.operation_id)

        restarted = self.workspace.start_iptc_empty_filter(3, 3)
        successful_batch = self.workspace.next_iptc_empty_filter_batch()
        completed = self.workspace.accept_iptc_empty_filter_batch(
            successful_batch.operation_id, ["three.jpg"]
        )

        self.assertNotEqual(
            restarted.filter_operation_id,
            failed_batch.operation_id,
        )
        self.assertEqual(completed.view_mode, PhotoWorkspaceViewMode.IPTC_EMPTY)
        self.assertEqual(completed.visible_paths, ("three.jpg",))

    def test_clearing_filter_restores_database_search_source_view(self) -> None:
        self.workspace.apply_database_search_matches(["two.jpg"])
        self.workspace.start_iptc_empty_filter(3, 3)
        batch = self.workspace.next_iptc_empty_filter_batch()
        self.workspace.accept_iptc_empty_filter_batch(batch.operation_id, ["one.jpg"])

        snapshot = self.workspace.clear_iptc_empty_filter()

        self.assertEqual(snapshot.view_mode, PhotoWorkspaceViewMode.DATABASE_SEARCH)
        self.assertEqual(snapshot.visible_paths, ("two.jpg",))
        self.assertEqual(snapshot.selected_paths, ("two.jpg",))

    def test_clearing_filter_restores_all_photos_and_invalidates_work(self) -> None:
        started = self.workspace.start_iptc_empty_filter(1, 1)
        batch = self.workspace.next_iptc_empty_filter_batch()

        snapshot = self.workspace.clear_iptc_empty_filter()
        stale_snapshot = self.workspace.accept_iptc_empty_filter_batch(
            batch.operation_id, ["one.jpg"]
        )

        self.assertIsNotNone(started.filter_operation_id)
        self.assertEqual(snapshot.visible_paths, ("one.jpg", "two.jpg", "three.jpg"))
        self.assertIsNone(snapshot.filter_operation_id)
        self.assertEqual(stale_snapshot, snapshot)

    def test_reload_invalidates_work_without_reusing_its_operation_identity(
        self,
    ) -> None:
        self.workspace.start_iptc_empty_filter(1, 1)
        stale_batch = self.workspace.next_iptc_empty_filter_batch()
        self.workspace.reload_paths(["four.jpg"])
        self.workspace.start_iptc_empty_filter(1, 1)

        snapshot = self.workspace.accept_iptc_empty_filter_batch(
            stale_batch.operation_id, ["one.jpg"]
        )

        self.assertEqual(snapshot.paths, ("four.jpg",))
        self.assertEqual(snapshot.filter_processed, 0)

    def test_indexed_refresh_stays_within_a_database_search_source_view(self) -> None:
        self.workspace.apply_database_search_matches(["two.jpg"])
        started = self.workspace.start_indexed_iptc_empty_filter()

        completed = self.workspace.accept_indexed_iptc_empty_filter(
            started.filter_operation_id or -1, ["one.jpg", "two.jpg"]
        )
        refreshed = self.workspace.refresh_indexed_iptc_empty_filter(["one.jpg"])
        restored = self.workspace.clear_iptc_empty_filter()

        self.assertEqual(completed.visible_paths, ("two.jpg",))
        self.assertEqual(refreshed.visible_paths, ())
        self.assertEqual(restored.view_mode, PhotoWorkspaceViewMode.DATABASE_SEARCH)
        self.assertEqual(restored.visible_paths, ("two.jpg",))

    def test_confirmed_tags_do_not_change_an_active_filter_view_until_user_restarts_it(
        self,
    ) -> None:
        self.workspace.start_iptc_empty_filter(3, 3)
        batch = self.workspace.next_iptc_empty_filter_batch()
        self.workspace.accept_iptc_empty_filter_batch(
            batch.operation_id, ["one.jpg", "two.jpg", "three.jpg"]
        )

        self.workspace.apply_iptc_emptiness({"one.jpg": False})

        snapshot = self.workspace.select_paths(["three.jpg"])

        self.assertEqual(
            snapshot.visible_paths,
            ("one.jpg", "two.jpg", "three.jpg"),
        )

        self.workspace.start_iptc_empty_filter(3, 3)
        batch = self.workspace.next_iptc_empty_filter_batch()
        refreshed = self.workspace.accept_iptc_empty_filter_batch(
            batch.operation_id, ["two.jpg", "three.jpg"]
        )

        self.assertEqual(refreshed.visible_paths, ("two.jpg", "three.jpg"))


if __name__ == "__main__":
    unittest.main()
