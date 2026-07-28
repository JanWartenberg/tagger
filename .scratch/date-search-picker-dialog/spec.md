# Date Search Picker Dialog

Status: needs-triage
Priority: low

## Problem Statement

The keyboard date-query grammar is efficient for keyboard-focused work but does not offer a discoverable mouse workflow for selecting a year, month, day, or date range.

## Desired Outcome

Provide a separate modal date-search dialog that writes a valid keyboard date expression into the existing database-search field and starts the existing indexed search. It must not introduce a second search state, query engine, or result view.

## Proposed Scope

- Offer year, month, day, and inclusive date-range selection through standard Qt controls.
- Convert the confirmed selection to the established `date:` grammar and invoke the existing search action.
- Keep `date:unknown` available as an explicit dialog option if it remains useful after UX design.
- Make the dialog usable with mouse and keyboard, while preserving the current keyboard-only search workflow unchanged.

## Open Triage Decisions

- Dialog entry point, label, and shortcut.
- Whether year/month controls are separate modes or derived from one calendar control.
- Range-picker interaction and validation feedback.
- Whether unknown-date search appears in the dialog.

## Constraints

- Reuse the active-root, background coordinator, database-search Photo Workspace, and persistent view indicator.
- Do not run SQLite or filesystem work on the Qt UI thread.
- Do not alter the date-query grammar or add a second search result mechanism.

## Out of Scope

- Replacing the keyboard date-query workflow.
- Calendar visualisation, saved searches, or global cross-root search.
