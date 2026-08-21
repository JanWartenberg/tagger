# 01 — Define Files-Pane Filter Block Visibility Workflow

Status: needs-triage
Priority: medium
Category: product-discovery
Milestone: M5 — Composable workspace filtering
Blocked by: None

## Goal

Specify a coherent show/hide workflow for the Files-pane filter block without concealing active conditions or changing Photo Workspace filtering behavior.

## Required Triage Before Implementation

- Decide the default visibility and whether the choice is session-local, workspace-local, or persisted across restarts.
- Decide the show/hide control, label, placement, command names, and shortcuts.
- Decide the collapsed presentation: input controls may be hidden, but active filter chips, their values, and individual clear controls must remain visible.
- Decide focus and keyboard behavior: hiding from a focused child, field-focus commands while hidden, Tab/Shift+Tab chip traversal, Escape, and Files-pane focus restoration.
- Decide behavior for active filter operations, validation feedback, empty results, and narrow window layouts.
- Confirm `MainWindow` owns presentation visibility and that no hide/show operation changes Photo Workspace conditions, membership, selection, active photo, or restoration state.
- Create separately scoped implementation work only after the workflow is approved.

## Constraints

- Preserve keyboard-driven access and a visible, individually removable representation for active Tags/Date, IPTC-empty, filename, and directory-exclusion conditions.
- Do not add a general query language, change filter semantics, trigger SQLite/filesystem work, or persist filter conditions.
- Keep UI work responsive.

## Comments

Created during directory-exclusion workflow triage. This is separate from directory-exclusion implementation scope; it concerns filter-block presentation, not filter-condition semantics.
