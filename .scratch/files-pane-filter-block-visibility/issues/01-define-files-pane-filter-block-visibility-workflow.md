# 01 — Define Files-Pane Filter Block Visibility Workflow

Status: completed
Priority: medium
Category: product-discovery
Milestone: M5 — Composable workspace filtering
Blocked by: None

## Goal

Specify a coherent show/hide workflow for the Files-pane filter block without concealing active conditions or changing Photo Workspace filtering behavior.

## Recorded Product Decisions

- Start open on each application launch, do not persist visibility, and retain it across Photo Workspace changes during the running session.
- Add an always-visible Qt standard-arrow toggle at the right of the top Files-pane row. Also provide `:togglefilters` and global `Ctrl+Shift+F` actions.
- Collapse only the bordered input/action block. Keep active chips, result/workspace information, progress, and empty-result guidance visible.
- Preserve drafts, validation state, debounce, and background operations while collapsed.
- Move focus from a hidden child to the photo list. Field-focus commands reopen before focusing; Escape retains its current field-specific behavior.
- Make every active condition an individually removable, keyboard-traversable chip with deterministic focus after removal.
- Keep visibility in `MainWindow`; toggling has no Photo Workspace state effect.

## Implementation Handoff

Implementation is scoped in [02 — Implement Collapsible Files-Pane Filter Block](02-implement-collapsible-files-pane-filter-block.md).

## Constraints

- Preserve keyboard-driven access and a visible, individually removable representation for active Tags/Date, IPTC-empty, filename, and directory-exclusion conditions.
- Do not add a general query language, change filter semantics, trigger SQLite/filesystem work, or persist filter conditions.
- Keep UI work responsive.

## Comments

Created during directory-exclusion workflow triage. This is separate from directory-exclusion implementation scope; it concerns filter-block presentation, not filter-condition semantics.

## Completion

The workflow was approved and handed off to issue 02.
