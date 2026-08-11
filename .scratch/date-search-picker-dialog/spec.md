# Date Search Picker Dialog

Status: wontfix
Priority: low

## Problem Statement

The keyboard date-query grammar is efficient for keyboard-focused work but does not offer a discoverable mouse workflow for selecting a year, month, day, or date range.

## Disposition

Won't fix. The selected Files-pane filter design exposes Date as a persistent input beside Tags rather than opening a modal picker. It compiles to the established `date:` grammar and uses the existing indexed-search result flow; it does not introduce a second query engine or result view.

## Retained Constraints

- Preserve the keyboard date-query grammar and `:search` contract.
- Reuse the active-root, background coordinator, database-search Photo Workspace, and view-indicator behavior.
- Do not run SQLite or filesystem work on the Qt UI thread.

## Out of Scope

- A modal calendar or range-picker UI.
- Calendar visualisation, saved searches, or global cross-root search.
