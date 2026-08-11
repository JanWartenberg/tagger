# Known-Tags Pane Evaluation

Status: completed
Priority: low

## Problem Statement

The persistent known-tags pane may not serve TAGGER's keyboard-driven workflow as well as autocomplete or a reduced alternative.

## Decision

Delete the persistent **Known tags** pane without a replacement surface. Maintainer evidence is that it was never used during regular TAGGER use; no distinct task beyond autocomplete justified consuming default layout space.

Keep the underlying recent and indexed tag cache. The add-keyword input uses that cache for `Tab` autocomplete independently of any visible widget.

## Completion

The pane, its commands, shortcuts, focus/navigation routes, refresh control, and pane-specific documentation are removed. The cache remains asynchronously refreshed after relevant index changes and workspace/root changes.

## Out of Scope

Changing the pane as incidental work in discovery or index maintenance.
