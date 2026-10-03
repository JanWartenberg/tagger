# Backlog

## Current milestone

**M9 — Repeatable real-file acceptance** is active following the maintainer's
acceptance of M8 and request to prioritize automated integration acceptance.

1. [Build and review the real-file integration suite](.scratch/windows-integration-suite/issues/01-build-real-file-integration-suite.md) — Windows regression verified in report 20261003T221813.709522Z; footer revision 02l and remaining visual checks pending.
2. [Subtle Scan setup toggle](.scratch/duplicate-photo-detection-and-tag-propagation/issues/02h-subtle-scan-setup-toggle.md) — completed; collapsed/expanded placement, Alt+U, selection preservation and reopening accepted on 2026-10-03; color previously accepted.
3. [Concise Duplicate review labels](.scratch/duplicate-photo-detection-and-tag-propagation/issues/02i-concise-duplicate-review-labels.md) — completed; reduced text density accepted on 2026-10-03. Concise UI text is now an AGENTS.md default.

Latest follow-ups:

- [02j — Navigation after Alt+U](.scratch/duplicate-photo-detection-and-tag-propagation/issues/02j-navigation-after-scan-setup-collapse.md) — completed; maintainer accepted.
- [02k — Side-by-side copy confirmation](.scratch/duplicate-photo-detection-and-tag-propagation/issues/02k-side-by-side-copy-confirmation.md) — completed; maintainer accepted.
- [02l — Compact result history](.scratch/duplicate-photo-detection-and-tag-propagation/issues/02l-compact-copy-result-history.md) — moved entirely into footer after the in-page design was rejected; Windows confirmation pending.

Maintainer accepted fixes 02e/02f/02g (menu contrast, scrollbar clearance, Copy
without Edit mode). Whether to remove the remaining Edit mode is undecided.

Maintainer confirmed Scan setup collapse and candidate filters work. Shared context
menu ticket 02d is completed: native actions and folder exclusion accepted on
2026-10-03; 02e records the accepted contrast fix.

M8 tag propagation is accepted and its ticket completed by maintainer decision.
Unrun manual checks were waived, not marked passed. Work remains on
`prototype/duplicate-review-ui`; integration into `main` needs a separate decision.

## Session handoff — checkpoint 2026-10-03

- Branch `prototype/duplicate-review-ui`. This handoff is included in the requested
  checkpoint commit; use `git log -1` for its hash. Base before the checkpoint:
  `3a0f706`. It includes UI code, tests, concise-text guidance and tickets 02e–02l.
- Accepted/completed: 02b, 02d and 02e–02k. Scan setup placement/reopening, Alt+U
  navigation without Edit mode, context-menu actions, scrollbar clearance, Copy
  without Edit mode, concise labels and side-by-side confirmation are accepted.
- Open: 02l (`needs-info`) awaits Windows regression and footer visual confirmation.
  The rejected in-page result widget is deleted entirely. One footer status/menu
  now holds save feedback, pending/failed/cancelled attention, outcomes, explicit
  failed-only retry and ignored-candidate restoration. Do not restore the strip.
- 02c remains `needs-info` only for explicit selection retention across candidate
  filter changes. Filter behavior was accepted; no implementation is pending.
- Integration-suite ticket/spec remain `needs-info`; M9 remains active. Remaining
  visual checks: footer, navigation/help, filter selection retention and larger
  font/display scale. Existing confirmations must not be requested again.
- Next: maintainer runs `python tests\acceptance\run.py` on Windows from repository
  root and checks the footer using `tests/acceptance/VISUAL_SMOKE.md`. Record the
  result in `tests/acceptance/REVIEW.md`, 02l and the integration-suite ticket.
- Latest Windows report `20261003T221813.709522Z`: twelve phases/32 cases, both
  backup modes, native lock/retry, process cleanup and workspace removal passed.
  It predates the footer revision. Reports are ignored local evidence, not committed.
- Footer revision validated locally: Ruff/format and diff checks pass; full
  offscreen pytest: 344 passed, four Windows skips, 33 subtests passed. Portable
  real-file report `tests/acceptance/reports/20261003T222741.128862Z/report.json`:
  ten phases/28 cases passed, both workspaces removed. Footer rendering inspected.
- Linux dev environment: `/tmp/tagger-venv` (activate, use `PYTHONPATH=.` and
  `QT_QPA_PLATFORM=offscreen`). Recreate if absent; repository `.venv` is Windows-only.
- Earlier full run segfaulted in a Qt callback; unchanged rerun passed. Cause remains
  undiagnosed; execution history is in `tests/acceptance/REVIEW.md`. Latest run passed.
- Edit mode removal remains undecided. Checkpoint commit is authorized; M9 closure,
  merge into `main` and push have not been requested.

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
