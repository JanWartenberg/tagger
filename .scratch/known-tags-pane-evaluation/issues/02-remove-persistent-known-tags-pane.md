# 02 — Remove Persistent Known-Tags Pane While Retaining Autocomplete Cache

Status: completed
Category: simplification
Priority: low
Milestone: M4 — Faster photo-finding and tagging workflows
Blocked by: 01

## Goal

Remove the unused visible Known tags surface without regressing tag autocomplete.

## Delivered

- Removed the pane, filter, refresh button, and pane-specific focus/navigation routes.
- Removed `:refresh`, `:focusfilter`, `:focustags`, `:knownnext`, `:knownprev`, and their shortcuts.
- Kept the asynchronous recent/indexed tag cache and made add-keyword `Tab` completion read it directly rather than a widget.
- Simplified two-pane focus navigation and removed obsolete documentation.

## Validation

- Offscreen coverage verifies the absent UI/actions and cached autocomplete before and after a completed cache refresh.
- `ruff check`, `ruff format --check`, the full offscreen suite (205 tests), and `git diff --check` passed.
