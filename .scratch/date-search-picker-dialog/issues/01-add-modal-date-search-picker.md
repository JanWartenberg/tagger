# 01 — Add Modal Date Search Picker

Status: needs-triage
Category: feature
Priority: low
Blocked by: None

## Goal

Give mouse-oriented users a modal UI for composing an existing date search without creating a parallel search model.

## Proposed Scope

- Add a modal Qt dialog for year, month, day, and inclusive date-range selection.
- Translate its confirmed selection into a valid `date:` expression.
- Set the existing database-search field and route through the existing search action.
- Cover dialog-to-query translation and MainWindow integration offscreen.

## Required Triage Before Implementation

- Final interaction design, entry point, and keyboard shortcut.
- Range-picker and unknown-date UX.
- User-facing validation and cancellation behavior.

## Constraints

- Depends on the completed keyboard date-query grammar being the sole search contract.
- Reuse existing background search and Photo Workspace result behavior.

## Comments

Created as a future follow-up while implementing the keyboard date-search variant. It is deliberately separate so the keyboard workflow does not wait for mouse UI design.
