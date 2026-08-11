# 01 — Record Files-Pane Filter UI Redesign

Status: completed
Category: enhancement
Priority: medium
Milestone: M4 — Faster photo-finding and tagging workflows
Blocked by: None

## Goal

Deliver the selected compact Files-pane filter UI without changing the Photo Workspace or indexed-search ownership boundaries.

## Delivered

- Grouped separate Tags, Date, and Filename controls with an `Aa` filename-case toggle and an Only-without-IPTC-tags condition.
- Added filter-box shortcuts: `Ctrl+T`/`Ctrl+D`/`Ctrl+F` for focus, `Ctrl+E` for IPTC-empty, and contextual `Alt+T`/`Alt+D`/`Alt+F`/`Alt+A`/`Alt+S`/`Alt+C`.
- Intersected Tags and Date through the existing indexed-search grammar; retained filename filtering as workspace-local.
- Replaced redundant inactive view text with workspace count, active-filter chips, and match/progress feedback.
- Retained Known tags, removed its Recursive scan control, and preserved `Ctrl+K` for its filter.
- Added the throwaway comparison prototype at `prototype/filter-ui-variants.html`.

## Validation

- `ruff check` and `ruff format --check` for changed Python files.
- Offscreen coverage for control layout, shortcuts, compound search, workspace count, filter presentation, and clear behavior.
- `git diff --check`.
