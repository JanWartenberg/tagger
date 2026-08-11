# 01 — Evaluate the Known-Tags Pane Workflow

Status: completed
Category: product-decision
Priority: low
Milestone: M4 — Faster photo-finding and tagging workflows
Blocked by: None

## Goal

Decide whether the persistent known-tags pane should remain, be reduced, be replaced, or be removed in favor of autocomplete.

## Resolution

Delete the persistent pane without a tab, view, or modal replacement. It had no recorded regular-use value beyond tag autocomplete, while consuming default layout space and adding pane-specific commands and navigation.

Retain the recent and indexed tag cache as an independent source for `Tab` autocomplete in the add-keyword input.

## Follow-up

- [02 — Remove Persistent Known-Tags Pane While Retaining Autocomplete Cache](02-remove-persistent-known-tags-pane.md)

## Comments

Created from `BACKLOG.md`. This ticket is evaluative; it does not authorize a behavior change by itself.

The Files-pane filter redesign initially retained **Known tags** as a local layout trade-off. Subsequent evaluation found no regular-use value for its visible surface. The pane is removed without replacement; its cached vocabulary remains solely for add-keyword autocomplete.
