# Move IPTC-empty filter state and stale-result rules into PhotoWorkspace

Status: ready-for-agent
Blocked by: 02

## Goal

Move logical IPTC-empty filter state from `MainWindow` into `PhotoWorkspace`, leaving metadata reads and thread scheduling in the Qt adapter.

## Acceptance criteria

- The module owns filter mode, logical progress, pending batches, operation identity, visibility, one-step preservation after tagging, and acceptance/rejection of filter results.
- The adapter asks the module for filter work, runs metadata reads off the UI thread, and submits every batch result back to the module.
- Results from an obsolete filter operation are ignored.
- A failed batch preserves the last successful membership, selection, and visibility; Qt remains responsible for status/error feedback.
- Progressive result behavior, scroll anchoring, and selection correction stay materially equivalent to the current application.
- No filter-state rules are duplicated in Qt code.
- Pure and Windows adapter tests pass.

## Out of scope

- Frozen-snapshot IPTC-empty semantics. That remains a later backlog item.
