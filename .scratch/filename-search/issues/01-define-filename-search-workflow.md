# 01 — Define Filename Search Within the Photo Workspace

Status: completed
Category: enhancement
Priority: medium
Milestone: M4 — Faster photo-finding and tagging workflows
Blocked by: None

## Goal

Define a filename-search workflow that narrows the current Photo Workspace without turning it into an index-wide filename search.

## Resolution

Triage selected a dedicated, visible workspace-local filename-filter field rather than `file:` syntax in the indexed tag/date search field. Matching is NFC-normalized basename substring matching, case-insensitive by default with an explicit `Aa` option. Filename, indexed-search, and IPTC-empty conditions combine using AND; their controls and a two-line-capable files-pane indicator expose every active condition.

The first delivery deliberately excludes directory/path matching, OR/NOT composition, globbing, regular expressions, persistence, and new SQLite work. The complete accepted behavior and architecture boundary are in [`../spec.md`](../spec.md).

## Follow-up

- [02 — Implement Workspace-Local Filename Filtering](02-implement-workspace-local-filename-filtering.md)

## Comments

Created at maintainer request. Grilling completed; the resolved behavior is ready for implementation.
