# 01 — Add Shift-J/K Multi-Selection Navigation

Status: ready-for-agent
Category: bug
Priority: high
Blocked by: None

## Problem

The Files pane supports extending a file selection with `Shift+Up` and
`Shift+Down`, but the equivalent keyboard-driven `Shift+j` and `Shift+k`
shortcuts do not extend the selection.

## Goal

Make `Shift+j` and `Shift+k` select the next or previous file while extending
the current multi-selection in the same way as `Shift+Down` and `Shift+Up`.

## Acceptance Criteria

- [ ] `Shift+j` extends the current Files-pane selection toward the next file.
- [ ] `Shift+k` extends the current Files-pane selection toward the previous file.
- [ ] Selection direction and anchor behavior match the existing Shift+Up/Down
      behavior, including reversing the extension.
- [ ] Plain `j` and `k` retain their existing single-selection navigation.
- [ ] The shortcuts work with filtered files and at selection boundaries without
      selecting hidden or out-of-range rows.
- [ ] Add deterministic regression coverage for both shortcuts and direction
      reversal.
- [ ] Existing Files-pane navigation and multi-selection tests continue to pass.

## Constraints

- Preserve the existing Photo Workspace selection model and Files-pane focus
  behavior.
- Do not change tag mutation scope or other `j`/`k` command behavior outside
  multi-selection in the Files pane.

## Validation

- Run the focused Files-pane keyboard and selection tests.
- Run the full test suite and Ruff for modified files.
