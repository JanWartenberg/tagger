# 02 — Investigate Final Filename-Filter Render Freeze

Status: needs-triage
Priority: high
Category: performance-investigation
Milestone: M4 — Faster photo-finding and tagging workflows
Blocked by: None

## Goal

Measure and remove the remaining application freeze when the debounced filename filter is applied to a Photo Workspace originating from roughly 3,000 files.

## Known Evidence

- The 700 ms debounce prevents blocking during ordinary typing but does not make the eventual filename-condition application responsive.
- The current renderer clears the `QListWidget` and recreates an item for every workspace path, including hidden paths. Earlier measurements showed the synchronous path grows from 0.40 s at 100 paths to 16.40 s at 3,000 paths.
- The IPTC-empty selection rebuild was independently fixed; this investigation must measure the final filename-filter application rather than regress that resolved selection path.

## Required Investigation

- Establish a checked-in, deterministic offscreen benchmark or regression test that waits for the debounced application and separately measures Photo Workspace predicate/snapshot time, Qt item construction, hiding, selection restoration, and event-loop blocking.
- Minimize the reproduction: determine whether the freeze is caused by retaining hidden items, repeated `QListWidgetItem` construction, selection/scroll restoration, mutation decoration, or another load-bearing step.
- Compare bounded rendering designs before implementation: updating only changed visibility, rendering only visible paths, batched/coalesced Qt updates with latest-result-wins cancellation, and a model-backed view if the existing widget cannot meet the response budget.
- Keep Qt object mutation on the UI thread. Do not move the existing SQLite, filesystem, metadata, or preview work into this interaction, and do not introduce a worker unless measurements show that the Qt-free filter computation—not rendering—exceeds the response budget.
- Create a separately scoped implementation ticket only after selecting an evidence-backed rendering design.

## Constraints

- Preserve literal basename-only matching, 700 ms debounce, immediate clear, explicit Enter/command/case-toggle behavior, and workspace-local AND composition with indexed-search and IPTC-empty conditions.
- Preserve selection, active photo, scroll restoration, empty-state feedback, mutation/unverified markers, keyboard navigation, and stale-result correctness.
- Do not add a global path search, SQLite filename query, filesystem rescan, globbing, regular expressions, persisted state, general boolean expressions, or a speculative thread-pool expansion.
