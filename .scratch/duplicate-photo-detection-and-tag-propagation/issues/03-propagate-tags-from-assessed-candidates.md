# 03 — Propagate Tags from Assessed Candidates

Status: ready-for-human
Category: feature
Priority: medium
Milestone: M8 — Duplicate candidate review and tag propagation
Blocked by: Windows/offscreen acceptance and maintainer approval

## Goal

Turn a positively assessed candidate group into an explicit, confirmed plan that
copies canonical tags from one readable, settled, non-empty source to selected
readable, settled, confirmed-empty targets through the existing reliable
tag-mutation workflow.

## Scope

- Refresh and validate source and target IPTC tags before confirmation.
- Reject paths with pending mutation intent rather than copying optimistic UI
  state.
- Preview the exact source tags and every selected target.
- Confirm source, targets, copied tags, and the current backup setting.
- Submit the copy through the existing tag-mutation coordinator.
- Keep per-target successful, failed, pending, and retryable outcomes visible in
  duplicate review.

## Accepted Interaction Decisions

- One source may copy to multiple eligible targets.
- Choosing a valid source preselects every eligible empty target in the group;
  each target can be deselected or reselected independently.
- Apply remains a two-stage action: `c` opens a complete preview, then `y`
  confirms while `n` or `Esc` cancels.
- Duplicate Review has an explicit Edit mode: `e` enters it and `Esc` leaves it.
  Single-character edit commands do not apply outside that mode or in text input.
- In Edit mode, `h`/`l` move between groups, `j`/`k` move through photos in grid
  reading order, `s` chooses the focused photo as source, `t` toggles it as a
  target, `c` starts copy confirmation, and `i` ignores the group.
- Visible key hints accompany the relevant group and photo controls.
- After confirmation, review advances immediately. The submitted group collapses
  to a compact status row with a spinner while writes are pending and a completed
  state when they finish.
- Partial failure does not interrupt the current review. A prominent failed row
  can be reopened to show per-target outcomes and retry only failed targets.
- Ignoring collapses the group to a recoverable `Ignored` row for the current
  scan and advances immediately; ignore persistence remains future work.

## Acceptance Criteria

- [ ] No metadata changes occur before the `c` preview is explicitly confirmed
      with `y`.
- [ ] Only a readable, non-empty source with no pending mutation can produce a
      propagation plan.
- [ ] Only readable, confirmed-empty targets with no pending mutation are
      eligible; targets that already contain tags or have unknown state cannot be
      selected.
- [ ] Choosing a source preselects all eligible targets and permits any subset to
      be deselected before confirmation.
- [ ] A plan cannot include paths outside its assessed scan result or use its
      source as a target.
- [ ] Source and target file state is refreshed before confirmation; changed or
      ineligible state invalidates the plan rather than applying stale data.
- [ ] Writes preserve canonical IPTC/XMP behavior, keyword limits, and the backup
      setting shown at confirmation.
- [ ] Confirmed work advances review and exposes pending, successful, failed, and
      retryable per-target outcomes through compact group rows.
- [ ] Partial failure retains successful writes and retries only failed targets.
- [ ] Edit-mode shortcuts, visible key hints, confirmation cancellation, and
      current-scan Ignore behavior match the accepted interaction decisions.
- [ ] Workspace or review navigation cannot redirect an old plan to new paths.
- [ ] Tests cover eligibility, default and subset target selection, confirmation
      cancellation, refreshed state, pending intent, stale plans, partial
      success, retry, compact status rows, and modal keyboard behavior.

## Out of Scope

- Copying into targets that already contain tags.
- Automatic propagation without assessment and explicit confirmation.
- File deletion, moves, or duplicate consolidation.
- Alternative detectors.

## Design Reference

See the accepted [design direction](../design-notes.md).

## Implementation and Validation

Implementation is on `prototype/duplicate-review-ui`; keep it isolated from
`main` until an explicit integration decision.

- Added a Qt-free, immutable propagation-plan API with fresh eligibility and
  scan-identity validation. Preview and confirmation both read file truth in
  background workers; writes and retries reject non-empty or unknown targets.
- Added Edit mode, default/subset target selection, exact copy confirmation,
  captured backup settings, advancing review, compact outcome rows, failed-target
  retry, and recoverable current-scan Ignore.
- Queued writes discarded on workspace replacement now report cancellation;
  failure restoration excludes paths already discarded from the queue.
- Automated coverage exercises the agreed propagation-plan, Qt adapter, and
  mutation-coordinator seams. It also covers bounded status/preview layouts and
  literal tag text in confirmation.
- Linux validation: `ruff check .`; `QT_QPA_PLATFORM=offscreen python -m pytest -q`
  (321 tests and 31 subtests passed). One full run hit the unchanged
  `test_latest_selection_is_not_queued_behind_stale_preview_loads` timing
  assertion; its isolated rerun and the subsequent full suite both passed.
- Pyright: new propagation/preview modules and the mutation coordinator have no
  errors. Existing `MainWindow` errors decreased from 182 to 177, with no new
  diagnostic categories or counts.
- Local two-axis review against `63bab54`: no documented-standard violations;
  one low-priority duplication advisory in preview/confirmation worker plumbing.
  Fixed the unbounded status-row layout, made large previews scrollable, and
  removed stale future-workflow wording.

## Remaining Human Acceptance

The acceptance checkboxes above remain pending final Windows validation rather
than claiming acceptance from Linux-only checks.

- Run and record the Windows/offscreen command in `tests/README.md`.
- Verify Edit-mode navigation, cancellation without writes, exact confirmed copy
  with backups on/off, partial failure and failed-only retry, current-scan Ignore
  restoration, and large result/target sets on disposable photo copies.
- Approve the delivered workflow; decide integration into `main` separately.
