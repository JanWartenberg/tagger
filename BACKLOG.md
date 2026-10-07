# Backlog

## Current milestone

**M9 — Repeatable real-file acceptance** is completed by maintainer acceptance
on 2026-10-04. No next active milestone has been selected.

- [Real-file integration suite](.scratch/windows-integration-suite/issues/01-build-real-file-integration-suite.md),
  [footer results (02l)](.scratch/duplicate-photo-detection-and-tag-propagation/issues/02l-compact-copy-result-history.md)
  and [filter selection retention (02c)](.scratch/duplicate-photo-detection-and-tag-propagation/issues/02c-default-to-actionable-candidates.md)
  are completed.
- Maintainer reported Windows runner PASSED:
  `tests/acceptance/reports/20261004T112405.399638Z/report.json`. Report
  contents were not independently inspected in this session.
- Remaining visual checks are accepted: navigation/focus/help, footer actions,
  filter selection retention, multi-target preview scrolling and cancel return.
  Window scaling passed; larger-font testing was explicitly waived and accepted
  because the font is unchanged.

## Current follow-up — 2026-10-07

- [Remember ignored duplicate candidates](.scratch/duplicate-photo-detection-and-tag-propagation/issues/04-remember-ignored-candidate-groups.md) selected for implementation after product rules were agreed.
- Persistence per index, evidence-based identity, read-only inspection, explicit
  restore and confirmed clear-all are implemented and verified locally.
- No new numbered milestone selected; ticket remains assigned to M-Future.
  Maintainer authorized commit after a successful quick acceptance check.
  Implementation and acceptance notes are committed together. Final verification:
  391 pytest passes/four Windows skips, Ruff/format and 14 real-file phases/38
  cases passed; two independent
  review rounds have no remaining findings. Report: `20261007T175150.109036Z`.
  Quick acceptance is maintainer-reported; full Windows automated results and
  detailed scaling checks remain unconfirmed. Inspect supplied Windows evidence
  before closing ticket 04; preserve the accepted quick check. No push requested.

## Session handoff — 2026-10-06

- Final focused Windows paired report supplied and independently inspected:
  median pair gains 10.7% read and 11.2% initial index, meeting the original
  thresholds. The 1,000-path adapter block is retained; refresh remains 200.
  No further Windows benchmark required; performance ticket completed.
- Timing claims apply to generated JPEGs with warm caches; Windows controls
  still fluctuate. Earlier rollback and measurement details are in the ticket.
- Portable real-file regression report `20261006T164501.259170Z` passed all
  ten phases/28 cases. Existing M9/UI acceptance remains valid; UI, writes and
  process lifecycle did not change.
- Pre-commit review fixed benchmark assertion disabling under Python `-O`,
  opaque index-reset failures and incomplete post-write metadata verification.
  Maintainer authorized review, fixes and commit; no push authorized.
- Previous preview-test instability remains undiagnosed; the final implementation
  run passed 374 tests/four Windows skips. Review validation is recorded in
  `tests/acceptance/REVIEW.md`.
- Review complete: all actionable findings fixed; Ruff/format, 380 offscreen
  tests/four Windows skips and diff checks passed. Performance work committed
  on main with maintainer authorization; no push. No active milestone selected.

## Session handoff — 2026-10-04

- Configurable default index root implemented as `:indexroot`; its ticket is
  completed and committed on main with maintainer authorization. Ruff, 355
  offscreen tests and ten portable real-file phases passed. Maintainer confirmed
  dialog opening and folder selection; native Windows automation and broader
  scaling checks remain unrun. No next active milestone was selected.
- Branch `main`; fast-forward integration of `prototype/duplicate-review-ui`
  through `3e6b356` completed after maintainer authorization and merge-risk checks.
  Acceptance and agent verification guidance are committed. No push performed.
- All M9 tickets are completed; preserve previous acceptances. The rejected
  in-page result widget stays deleted; outcomes/retry/restoration use the footer.
- Next decision: choose future work; no active milestone remains.
  Removing the remaining Edit mode remains undecided, with no implementation ticket.
- Linux dev environment: `/tmp/tagger-venv` (activate, use `PYTHONPATH=.` and
  `QT_QPA_PLATFORM=offscreen`). Recreate if absent; repository `.venv` is Windows-only.
- Last local implementation validation: Ruff/format and diff checks passed;
  pre-merge full offscreen pytest: 344 passed, four Windows skips. Portable
  report `20261004T122111.114146Z` passed (ten phases). Standards/spec review
  found no merge blockers. See `tests/acceptance/REVIEW.md` for follow-up concerns.
- Earlier full run segfaulted in a Qt callback; unchanged rerun passed. Cause
  remains undiagnosed; history is in `tests/acceptance/REVIEW.md`.

## Future milestone

**M-Future — Unscheduled opportunities** means sometime after M8, without a target date.

- [AI tag-suggestion boundary](.scratch/ai-assisted-tag-suggestions/issues/01-define-ai-tag-suggestion-boundary.md) remains needs-triage and is outside M8.
- [Remember ignored duplicate candidates](.scratch/duplicate-photo-detection-and-tag-propagation/issues/04-remember-ignored-candidate-groups.md) is the selected follow-up to M8 (implemented; Windows acceptance pending).

## Historical milestones

M1 was confirmed by the maintainer as the initial MVP. M2–M7 names are recorded
in existing ticket metadata; their tickets have terminal dispositions (completed
or wontfix). This is not a list of active work.

| Milestone | Recorded scope |
| --- | --- |
| M1 | MVP — Get TAGGER running end to end |
| M2 | Reliable, scalable index operations |
| M3 | Metadata integrity and cache-backed IPTC workflow |
| M4 | Faster photo-finding and tagging workflows |
| M5 | Composable workspace filtering |
| M6 | Maintainability and performance |
| M7 | Startup correctness and autocomplete navigation |

## High-priority cross-cutting work

GitHub publication readiness is tracked separately from M8 as cross-cutting
repository preparation:

- [Prepare TAGGER for GitHub publication](.scratch/github-publication-readiness/issues/01-prepare-tagger-for-github.md) — completed, high priority

Specs and individual tickets live in `.scratch/`; this file records milestone
selection rather than duplicating ticket status.
