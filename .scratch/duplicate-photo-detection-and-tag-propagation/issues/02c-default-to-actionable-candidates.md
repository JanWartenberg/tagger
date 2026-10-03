# 02c — Default Duplicate review to actionable candidates

Status: needs-info
Category: feature
Priority: medium
Milestone: M9 — Repeatable real-file acceptance
Blocked by: explicit selection-retention confirmation across candidate filters

## Goal

Avoid dead-end candidate groups in the tag-copy workflow, including the reported
pair with canonical tags `FN, Eisvogel, Spektiv` and `Eisvogel`: neither photo is
an empty target. Keep the detector's full findings available for inspection.

## Accepted behavior

- Default to groups with a readable tagged source and a different readable empty
  target in confirmed scan evidence. This is presentation filtering, not a new
  detector, and does not bypass pending-intent/fresh-file write guards.
- Add `Show all candidates` next to the existing non-empty-group checkbox.
- The non-empty filter applies only in all-candidates mode; disable it in the
  default actionable-only mode, preserving its choice for later reactivation.
- In all mode, checked non-empty filter excludes only wholly readable empty groups;
  groups with unknown tags remain inspectable.
- Preserve source/target choices, ignored/submitted state and footer results while
  changing filters. Summarize shown/total groups and the effective mode.
- Explain a filtered empty queue and label non-actionable groups inspection-only.
  No overwriting or merging into tagged targets.
- `Alt+A` and `:toggleallduplicates` control all mode only in Duplicate review;
  `Alt+E` remains the non-empty shortcut when its filter is available.

## Delivery

Implemented and covered through public MainWindow scan/widget/keyboard seams.
Fixtures include the reported fully tagged pair, empty-only groups, unknown source
or target metadata, and copyable groups. Tests cover filter combinations, retained
choices, inspection-only copy refusal, view-scoped shortcuts and help.

Maintainer subsequently confirmed that candidate filters work on Windows.
Queue scrollbar clipping was reported separately and is tracked in 02f; detailed
selection-retention acceptance was not separately reported. This is a follow-up
to accepted M8, not a reopening of its propagation policy.

Session handoff: 02f is now accepted. Concise filter/summary wording is tracked in
02i; filter semantics have not changed. No implementation work remains here;
confirm detailed selection retention at final visual acceptance.

## Checkpoint handoff — 2026-10-03

Implemented in the checkpoint on `prototype/duplicate-review-ui`; no code work
remains. General filter behavior is accepted. Only the explicit check that
source/target choices survive Show all/non-empty filter changes remains open.
Final results are now in the footer (02l), not in status rows.
