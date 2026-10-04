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

## Session handoff — 2026-10-04

- Branch `prototype/duplicate-review-ui`; implementation checkpoint `84a36f7`.
  This documentation commit records acceptance and agent verification guidance.
  The maintainer authorized local integration into `main` after merge-risk checks.
  Push has not been requested.
- All M9 tickets are completed; preserve previous acceptances. The rejected
  in-page result widget stays deleted; outcomes/retry/restoration use the footer.
- Next decision: integrate the accepted branch into `main` or choose future work.
  Removing the remaining Edit mode remains undecided, with no implementation ticket.
- Linux dev environment: `/tmp/tagger-venv` (activate, use `PYTHONPATH=.` and
  `QT_QPA_PLATFORM=offscreen`). Recreate if absent; repository `.venv` is Windows-only.
- Last local implementation validation: Ruff/format and diff checks passed;
  full offscreen pytest: 344 passed, four Windows skips, 33 subtests passed.
  Portable report `20261003T222741.128862Z` passed. Tests are not repeated for
  acceptance documentation changes.
- Earlier full run segfaulted in a Qt callback; unchanged rerun passed. Cause
  remains undiagnosed; history is in `tests/acceptance/REVIEW.md`.

## Future milestone

**M-Future — Unscheduled opportunities** means sometime after M8, without a target date.

- [Performance follow-up](.scratch/performance-follow-up-real-workload/issues/01-measure-and-optimize-next-real-workload-bottleneck.md) remains deferred until one to three other topics have been completed.
- [Configurable default index root](.scratch/configurable-default-index-root/issues/01-add-configurable-default-index-root.md) is medium priority and remains unscheduled.
- [AI tag-suggestion boundary](.scratch/ai-assisted-tag-suggestions/issues/01-define-ai-tag-suggestion-boundary.md) remains needs-triage and is outside M8.
- [Remember ignored duplicate candidates](.scratch/duplicate-photo-detection-and-tag-propagation/issues/04-remember-ignored-candidate-groups.md) is a low-priority follow-up to M8.

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
