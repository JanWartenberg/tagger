# Backlog

## Current milestone

**M6 — Maintainability and performance** is active. It contains exactly two tickets:

- [Refactor for maintainability](.scratch/maintainability-refactoring/issues/01-simplify-and-deduplicate-code.md)
- [Profile and optimize loading, saving, and indexing](.scratch/loading-saving-indexing-performance/issues/01-profile-and-optimize-core-workflows.md)

Capture the performance baseline before substantial refactoring; then use small,
reviewable refactoring and optimization steps. These are two workstreams, not a
requirement to finish all refactoring before beginning performance work.

## Future milestone

**M-Future — Unscheduled opportunities** means sometime after M6, without a target date.

- [AI tag-suggestion boundary](.scratch/ai-assisted-tag-suggestions/issues/01-define-ai-tag-suggestion-boundary.md) remains needs-triage and is outside M6.

## Historical milestones

M1 was confirmed by the maintainer as the initial MVP. M2–M5 names are recorded
in existing ticket metadata; their tickets have terminal dispositions (completed
or wontfix). This is not a list of active work.

| Milestone | Recorded scope |
| --- | --- |
| M1 | MVP — Get TAGGER running end to end |
| M2 | Reliable, scalable index operations |
| M3 | Metadata integrity and cache-backed IPTC workflow |
| M4 | Faster photo-finding and tagging workflows |
| M5 | Composable workspace filtering |

Specs and individual tickets live in `.scratch/`; this file records milestone
selection rather than duplicating ticket status.
