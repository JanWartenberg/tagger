from __future__ import annotations

import unittest

from exif_tool import KeywordState
from services.pending_tag_mutation import (
    MutationStatus,
    PendingTagMutationCoordinator,
    TagIntent,
)


class PendingTagMutationCoordinatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.path = "C:/photos/one.jpg"
        self.confirmed = KeywordState(["before"], ["before"])
        self.requested = KeywordState(["after"], ["after"])
        self.coordinator = PendingTagMutationCoordinator()
        self.coordinator.remember_confirmed({self.path: self.confirmed})

    def test_requested_metadata_is_pending_until_the_write_succeeds(self) -> None:
        mutation = self.coordinator.begin_intents(
            {self.path: [TagIntent.remove("before"), TagIntent.add("after")]}
        )

        self.assertEqual(self.coordinator.metadata_for(self.path), self.requested)
        self.assertEqual(self.coordinator.status_for(self.path), MutationStatus.PENDING)

        self.coordinator.succeed(mutation, {self.path: self.requested})

        self.assertEqual(self.coordinator.metadata_for(self.path), self.requested)
        self.assertIsNone(self.coordinator.status_for(self.path))
        self.assertEqual(self.coordinator.confirmed_for(self.path), self.requested)

    def test_field_resolution_is_not_retryable_after_three_attempts(self) -> None:
        target = KeywordState(["after"], ["after"])
        mutation = self.coordinator.begin_intents(
            {self.path: [TagIntent.replace_fields(target)]}
        )

        self.coordinator.fail(mutation, attempts_by_path={self.path: 3})

        self.assertIsNone(self.coordinator.retry_failed([self.path]))
        self.assertEqual(self.coordinator.status_for(self.path), MutationStatus.FAILED)

    def test_later_pending_mutation_is_recomputed_after_an_earlier_failure(
        self,
    ) -> None:
        first = self.coordinator.begin_intents({self.path: [TagIntent.add("first")]})
        second = self.coordinator.begin_intents({self.path: [TagIntent.add("second")]})

        self.coordinator.fail(first)

        self.assertEqual(
            self.coordinator.metadata_for(self.path),
            KeywordState(["before", "second"], ["before", "second"]),
        )
        self.assertEqual(self.coordinator.status_for(self.path), MutationStatus.PENDING)

        self.coordinator.succeed(
            second,
            {self.path: KeywordState(["before", "second"], ["before", "second"])},
        )

        self.assertEqual(
            self.coordinator.confirmed_for(self.path),
            KeywordState(["before", "second"], ["before", "second"]),
        )
        self.assertEqual(self.coordinator.status_for(self.path), MutationStatus.FAILED)

    def test_partial_batch_confirms_successes_and_retries_only_selected_failures(
        self,
    ) -> None:
        failed_path = "C:/photos/two.jpg"
        failed_confirmed = KeywordState(["two-before"], ["two-before"])
        self.coordinator.remember_confirmed({failed_path: failed_confirmed})
        mutation = self.coordinator.begin_intents(
            {
                self.path: [TagIntent.add("added")],
                failed_path: [TagIntent.add("added")],
            }
        )

        self.coordinator.succeed(
            mutation,
            {self.path: KeywordState(["before", "added"], ["before", "added"])},
        )
        restored = self.coordinator.fail(mutation, [failed_path])

        self.assertEqual(
            self.coordinator.confirmed_for(self.path),
            KeywordState(["before", "added"], ["before", "added"]),
        )
        self.assertIsNone(self.coordinator.status_for(self.path))
        self.assertEqual(restored, {failed_path: failed_confirmed})
        self.assertEqual(
            self.coordinator.status_for(failed_path), MutationStatus.FAILED
        )

        retry = self.coordinator.retry_failed([failed_path])

        self.assertIsNotNone(retry)
        assert retry is not None
        self.assertEqual(set(retry.intents_by_path), {failed_path})
        self.assertEqual(
            self.coordinator.metadata_for(failed_path),
            KeywordState(["added", "two-before"], ["added", "two-before"]),
        )
        self.assertEqual(
            self.coordinator.status_for(failed_path), MutationStatus.PENDING
        )
        self.assertIsNone(self.coordinator.retry_failed([self.path]))

    def test_retry_ignores_pending_mutations_for_selected_photos(self) -> None:
        failed = self.coordinator.begin_intents({self.path: [TagIntent.add("failed")]})
        self.coordinator.fail(failed)
        pending = self.coordinator.begin_intents({self.path: [TagIntent.add("later")]})

        retry = self.coordinator.retry_failed([self.path])

        self.assertIsNotNone(retry)
        assert retry is not None
        self.assertEqual(
            retry.apply(self.path, self.confirmed),
            KeywordState(["before", "failed"], ["before", "failed"]),
        )
        self.assertEqual(self.coordinator.status_for(self.path), MutationStatus.PENDING)
        self.assertEqual(
            self.coordinator.metadata_for(self.path),
            KeywordState(["before", "failed", "later"], ["before", "failed", "later"]),
        )
        self.assertNotEqual(retry.sequence, pending.sequence)

    def test_later_intent_supersedes_only_the_matching_failed_tag_intent(self) -> None:
        failed = self.coordinator.begin_intents(
            {self.path: [TagIntent.add("A"), TagIntent.add("B")]}
        )
        self.coordinator.fail(failed)

        later = self.coordinator.begin_intents({self.path: [TagIntent.add("a")]})
        self.coordinator.succeed(
            later, {self.path: KeywordState(["A", "before"], ["A", "before"])}
        )

        retry = self.coordinator.retry_failed([self.path])

        self.assertIsNotNone(retry)
        assert retry is not None
        self.assertEqual(
            retry.apply(self.path, self.coordinator.confirmed_for(self.path)),
            KeywordState(["A", "B", "before"], ["A", "B", "before"]),
        )

    def test_later_remove_intent_case_insensitively_supersedes_failed_add(self) -> None:
        failed = self.coordinator.begin_intents({self.path: [TagIntent.add("A")]})
        self.coordinator.fail(failed)

        later = self.coordinator.begin_intents({self.path: [TagIntent.remove("a")]})
        self.coordinator.succeed(later, {self.path: self.confirmed})

        self.assertIsNone(self.coordinator.status_for(self.path))
        self.assertIsNone(self.coordinator.retry_failed([self.path]))

    def test_failed_state_is_session_only_and_survives_an_absent_workspace(
        self,
    ) -> None:
        mutation = self.coordinator.begin_intents(
            {self.path: [TagIntent.add("unresolved")]}
        )
        self.coordinator.fail(mutation)

        self.assertEqual(self.coordinator.status_for(self.path), MutationStatus.FAILED)
        self.assertIsNone(PendingTagMutationCoordinator().status_for(self.path))

    def test_failed_write_restores_confirmed_metadata_and_marks_the_photo_failed(
        self,
    ) -> None:
        mutation = self.coordinator.begin_intents(
            {self.path: [TagIntent.remove("before"), TagIntent.add("after")]}
        )

        restored = self.coordinator.fail(mutation)

        self.assertEqual(restored, {self.path: self.confirmed})
        self.assertEqual(self.coordinator.metadata_for(self.path), self.confirmed)
        self.assertEqual(self.coordinator.status_for(self.path), MutationStatus.FAILED)
        self.assertEqual(self.coordinator.confirmed_for(self.path), self.confirmed)


if __name__ == "__main__":
    unittest.main()
