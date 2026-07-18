from __future__ import annotations

import unittest

from exif_tool import KeywordState
from services.pending_tag_mutation import MutationStatus, PendingTagMutationCoordinator


class PendingTagMutationCoordinatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.path = "C:/photos/one.jpg"
        self.confirmed = KeywordState(["before"], ["before"])
        self.requested = KeywordState(["after"], ["after"])
        self.coordinator = PendingTagMutationCoordinator()
        self.coordinator.remember_confirmed({self.path: self.confirmed})

    def test_requested_metadata_is_pending_until_the_write_succeeds(self) -> None:
        mutation = self.coordinator.begin({self.path: self.requested})

        self.assertEqual(self.coordinator.metadata_for(self.path), self.requested)
        self.assertEqual(self.coordinator.status_for(self.path), MutationStatus.PENDING)

        self.coordinator.succeed(mutation, {self.path: self.requested})

        self.assertEqual(self.coordinator.metadata_for(self.path), self.requested)
        self.assertIsNone(self.coordinator.status_for(self.path))
        self.assertEqual(self.coordinator.confirmed_for(self.path), self.requested)

    def test_failed_write_restores_confirmed_metadata_and_marks_the_photo_failed(
        self,
    ) -> None:
        mutation = self.coordinator.begin({self.path: self.requested})

        restored = self.coordinator.fail(mutation)

        self.assertEqual(restored, {self.path: self.confirmed})
        self.assertEqual(self.coordinator.metadata_for(self.path), self.confirmed)
        self.assertEqual(self.coordinator.status_for(self.path), MutationStatus.FAILED)
        self.assertEqual(self.coordinator.confirmed_for(self.path), self.confirmed)


if __name__ == "__main__":
    unittest.main()
