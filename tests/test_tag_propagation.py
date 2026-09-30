"""Behavior at the confirmed propagation-plan seam."""

import unittest
from dataclasses import replace

from tagger_app.exif_tool import KeywordState
from tagger_app.services.duplicate_detection import (
    CandidateGroup,
    CandidateMember,
    ScanResult,
)
from tagger_app.services.pending_tag_mutation import MutationStatus
from tagger_app.services.tag_propagation import (
    TagPropagationPlan,
    prepare_propagation,
    validate_propagation,
)


class TagPropagationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.result = ScanResult(
            "scan",
            "timestamp",
            (
                CandidateGroup(
                    "group",
                    (
                        CandidateMember(
                            "source", "time", "EXIF:DateTimeOriginal", ("Holiday",)
                        ),
                        CandidateMember("empty", "time", "EXIF:DateTimeOriginal"),
                        CandidateMember("also-empty", "time", "EXIF:DateTimeOriginal"),
                        CandidateMember(
                            "tagged", "time", "EXIF:DateTimeOriginal", ("Other",)
                        ),
                        CandidateMember(
                            "unknown", "time", "EXIF:DateTimeOriginal", (), False
                        ),
                    ),
                ),
            ),
            (),
            (),
            5,
            5,
            True,
        )
        self.states = {
            "source": KeywordState(["Holiday"], ["not canonical"]),
            "empty": KeywordState([], []),
            "also-empty": KeywordState([], ["old mirror"]),
            "tagged": KeywordState(["Other"], []),
            "unknown": KeywordState([], [], iptc_readable=False),
        }
        self.statuses: dict[str, MutationStatus] = {}

    def prepare(
        self, source: str = "source", targets: tuple[str, ...] = ("empty",)
    ) -> TagPropagationPlan:
        return prepare_propagation(
            self.result,
            "group",
            source,
            targets,
            True,
            self.states.__getitem__,
            self.statuses.get,
        )

    def test_plan_copies_exact_canonical_tags_and_selected_subset(self) -> None:
        plan = self.prepare()
        self.assertEqual(
            (plan.source, plan.targets, plan.tags, plan.keep_backup),
            ("source", ("empty",), ("Holiday",), True),
        )
        self.assertEqual(
            self.prepare(targets=("empty", "also-empty")).targets,
            ("empty", "also-empty"),
        )
        self.assertEqual(self.states["empty"].iptc, [])

    def test_ineligible_targets_cannot_produce_a_plan(self) -> None:
        for target in ("tagged", "unknown", "source", "outside"):
            with self.subTest(target=target), self.assertRaises(ValueError):
                self.prepare(targets=(target,))
        with self.assertRaises(ValueError):
            self.prepare(targets=())

    def test_only_a_readable_nonempty_source_is_eligible(self) -> None:
        for source in ("empty", "unknown", "outside"):
            with self.subTest(source=source), self.assertRaises(ValueError):
                self.prepare(source=source, targets=("also-empty",))

    def test_pending_intent_is_rejected_for_source_and_target(self) -> None:
        for path in ("source", "empty"):
            with self.subTest(path=path):
                self.statuses = {path: MutationStatus.PENDING}
                with self.assertRaisesRegex(ValueError, "Pending tag changes"):
                    self.prepare()

    def test_unknown_or_changed_fresh_metadata_invalidates_assessment(self) -> None:
        for path in ("source", "empty"):
            original = self.states[path]
            for state in (
                KeywordState(["Changed"], []),
                KeywordState([], [], iptc_readable=False),
            ):
                with (
                    self.subTest(path=path, state=state),
                    self.assertRaises(ValueError),
                ):
                    self.states[path] = state
                    self.prepare()
            self.states[path] = original

    def test_confirmation_rejects_superseded_scan_and_tampered_preview(self) -> None:
        plan = self.prepare()
        for stale_result in (
            replace(self.result, scan_id="new-scan"),
            replace(self.result, detector_id="new-method"),
        ):
            with self.subTest(result=stale_result), self.assertRaises(ValueError):
                validate_propagation(
                    plan, stale_result, self.states.__getitem__, self.statuses.get
                )
        with self.assertRaises(ValueError):
            validate_propagation(
                replace(plan, tags=("Invented",)),
                self.result,
                self.states.__getitem__,
                self.statuses.get,
            )

    def test_confirmation_refreshes_state_and_rechecks_pending_intent(self) -> None:
        plan = self.prepare()
        refreshed = validate_propagation(
            plan, self.result, self.states.__getitem__, self.statuses.get
        )
        self.assertEqual(refreshed["empty"].iptc, [])
        self.statuses["empty"] = MutationStatus.PENDING
        with self.assertRaises(ValueError):
            validate_propagation(
                plan, self.result, self.states.__getitem__, self.statuses.get
            )
        self.statuses.clear()
        self.states["source"] = KeywordState(["External"], [])
        with self.assertRaises(ValueError):
            validate_propagation(
                plan, self.result, self.states.__getitem__, self.statuses.get
            )

    def test_keyword_limits_are_validated_before_preview(self) -> None:
        source = self.result.groups[0].members[0]
        too_long = "é" * 33
        group = replace(
            self.result.groups[0],
            members=(
                replace(source, iptc_tags=(too_long,)),
                *self.result.groups[0].members[1:],
            ),
        )
        self.result = replace(self.result, groups=(group,))
        self.states["source"] = KeywordState([too_long], [])
        with self.assertRaisesRegex(ValueError, "66/64 UTF-8 bytes"):
            self.prepare()
