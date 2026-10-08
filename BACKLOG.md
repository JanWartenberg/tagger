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

## Current follow-up — direct Duplicate review shortcuts

- [Remove Duplicate review Edit mode](.scratch/duplicate-photo-detection-and-tag-propagation/issues/05-remove-duplicate-review-edit-mode.md) completed after local verification and Windows acceptance on 2026-10-08.
- Single keys act directly, typing and copy confirmation remain protected; no
  new numbered milestone selected. Maintainer authorized commit on 2026-10-08;
  implementation and acceptance records are included together. No push requested.
- 396 pytest passes/four Windows skips; Ruff/format and fourteen real-file phases/
  40 cases passed, including direct review/list keyboard events and Ctrl+I.
  Latest portable report: `20261008T161805.450253Z`.
  Windows report `20261008T161432.936635Z` independently inspected: sixteen
  phases/44 cases and native cleanup passed. After the underline fix, maintainer
  confirmed AT-04 passed. Final checklist: six PASS / zero FAIL / zero
  NOT ASSESSED; ACCEPT. Ticket 05 completed; no remaining acceptance.
- Header follow-up: collapsed Scan setup is immediately left of Ignored
  candidates; `Ctrl+I` opens that list, with tooltip/help coverage.
  Ignored-list `j/k/r/a/c` shortcuts,
  Escape close and button mnemonics/tooltips are also implemented.
- Maintainer confirmed ignoring/resetting work; preserve that acceptance.
- Second review completed on 2026-10-08: fixed modal-focus and initial-preview
  test races; 20 repeated cases and full Linux suite (396/four skips) passed.
  Ruff 0.12/0.16 and format passed; maintainer confirmed Windows Ruff passes.
  Maintainer supplied the final Windows run: 400 tests passed in 44.03s; both
  Ruff commands passed. No remaining verification or review findings; ready
  for the authorized commit. Prior feature acceptance stays accepted.

## Session handoff — 2026-10-07

- [Remember ignored duplicate candidates](.scratch/duplicate-photo-detection-and-tag-propagation/issues/04-remember-ignored-candidate-groups.md) completed after maintainer quick acceptance and independently inspected Windows verification.
- Implementation and original acceptance notes committed as `1d6d909` with
  maintainer authorization. No push requested. Windows acceptance updates are
  documentation-only and remain uncommitted.
- Linux: 391 pytest passes/four Windows skips, Ruff/format and fourteen real-file
  phases/38 cases passed; two independent review rounds have no remaining findings.
- Windows report `20261007T200507.473386Z`: sixteen phases/42 cases passed on clean
  commit `1d6d909`, both backup settings, sharing-lock retry, native cleanup and
  workspace removal verified; all harness hashes match tracked scripts.
- Prior quick acceptance is maintainer-reported. Detailed scaling observations
  remain unreported, not claimed passed or waived; do not repeat the accepted check.
- No next active milestone selected. AI suggestion boundary remains needs-triage.

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
  Edit mode removal was undecided at that checkpoint; subsequently approved
  and implemented under ticket 05 on 2026-10-07.
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
