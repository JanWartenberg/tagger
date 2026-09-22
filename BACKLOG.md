# Backlog

## Current milestone

**M8 — Duplicate candidate review and tag propagation** is active. Its tickets
are ordered by dependency:

1. [Implement duplicate-candidate detection foundation](.scratch/duplicate-photo-detection-and-tag-propagation/issues/01-implement-duplicate-candidate-detection-foundation.md) — ready for agent
2. [Build duplicate-candidate assessment view](.scratch/duplicate-photo-detection-and-tag-propagation/issues/02-build-duplicate-candidate-assessment-view.md) — needs triage; blocked by ticket 01
3. [Propagate tags from assessed candidates](.scratch/duplicate-photo-detection-and-tag-propagation/issues/03-propagate-tags-from-assessed-candidates.md) — needs triage; blocked by ticket 02

Implement the read-only detection foundation first. Keep detection, human
assessment, and metadata mutation as separate delivery stages.

## Future milestone

**M-Future — Unscheduled opportunities** means sometime after M8, without a target date.

- [Performance follow-up](.scratch/performance-follow-up-real-workload/issues/01-measure-and-optimize-next-real-workload-bottleneck.md) remains deferred until one to three other topics have been completed.
- [Configurable default index root](.scratch/configurable-default-index-root/issues/01-add-configurable-default-index-root.md) is medium priority and remains unscheduled.
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

- [Prepare TAGGER for GitHub publication](.scratch/github-publication-readiness/issues/01-prepare-tagger-for-github.md) — ready for agent, high priority

Specs and individual tickets live in `.scratch/`; this file records milestone
selection rather than duplicating ticket status.
