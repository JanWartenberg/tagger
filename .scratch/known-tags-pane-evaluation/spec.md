# Known-Tags Pane Evaluation

Status: needs-triage
Priority: low

## Problem Statement

The persistent known-tags pane may not serve TAGGER's keyboard-driven workflow as well as autocomplete or a reduced alternative.

## Current Position

The Files-pane filter redesign leaves **Known tags** in place as a local layout trade-off: it reclaims space from redundant filter/status text and the Recursive scan control, while `Ctrl+K` preserves a direct keyboard workflow. This does not decide the pane's longer-term product role.

## Open Triage Decisions

- Which current workflows depend on the pane versus autocomplete.
- Evaluation criteria and user feedback needed before a product decision.
- Whether the pane should remain, be reduced, replaced, or removed; create separately scoped implementation work only after that decision.

## Out of Scope

Changing the pane as incidental work in discovery or index maintenance.
