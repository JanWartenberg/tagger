# 01 — Evaluate the Known-Tags Pane Workflow

Status: needs-triage
Category: product-decision
Priority: low
Milestone: M4 — Faster photo-finding and tagging workflows
Blocked by: None

## Goal

Decide whether the persistent known-tags pane should remain, be reduced, be replaced, or be removed in favor of autocomplete.

## Required Triage Before Implementation

- Establish evaluation evidence and decision criteria.
- Identify keyboard workflows that must remain supported.
- Split any chosen product change into implementation ticket(s).

## Comments

Created from `BACKLOG.md`. This ticket is evaluative; it does not authorize a behavior change by itself.

The Files-pane filter redesign retained **Known tags** as a local layout trade-off:
space came from redundant filter/status text and the Recursive scan control,
and `Ctrl+K` preserves a direct keyboard workflow. This was not a durable
product decision to retain the pane. Reopened for separate evaluation of
whether it should remain, be reduced, replaced, or removed.
