# Backlog

## Current milestone

**M9 — Repeatable real-file acceptance** is active following the maintainer's
acceptance of M8 and request to prioritize automated integration acceptance.

1. [Build and review the real-file integration suite](.scratch/windows-integration-suite/issues/01-build-real-file-integration-suite.md) — high priority, needs-info for Windows validation; normal paths and cleanup passed on Windows; refusal and sharing-lock/retry slice implemented in `tests/acceptance/`, with portable refusals passing on Linux. Next: expanded Windows run, then visual smoke/acceptance.
2. [Make Scan setup collapsible](.scratch/duplicate-photo-detection-and-tag-propagation/issues/02b-collapse-scan-setup.md) — medium-priority UI follow-up.

M8 tag propagation is accepted and its ticket completed by maintainer decision.
Unrun manual checks were waived, not marked passed. Work remains on
`prototype/duplicate-review-ui`; integration into `main` needs a separate decision.

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
