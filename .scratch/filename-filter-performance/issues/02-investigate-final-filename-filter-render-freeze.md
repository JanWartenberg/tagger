# 02 — Investigate Final Filename-Filter Render Freeze

Status: completed
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

## Findings

- `python3 tests/profile_filename_filter.py` is the deterministic red regression harness: 3,000 paths take 5.031 s and invoke `_filtered_visible()` 3,001 times. `PhotoWorkspace.snapshot()` calls `_filtered_visible()` inside its per-path visible-membership generator, making final filter application quadratic before Qt rendering begins.
- The original offscreen UI path takes 22.589 s for the same 3,000-path final filter. Replacing only the snapshot derivation with a single computed membership reduces it to 8.593 s.
- The remaining delay is redundant canonicalization: `_set_file_mutation_indicator()` resolves every row path, and `_find_item_by_path()` resolves every row while restoring the selected final match. With those operations replaced only in the measurement, final application is 0.038 s. Batched rendering with the existing 250-row size returns immediately but each decorated batch takes about 0.4 s and final lookup adds about 4.3 s; it is not required after removing the identified work.
- Decision: no worker, model-backed view, or new rendering protocol. Keep Qt work on the UI thread; implement one derived-membership calculation per snapshot plus canonical file-item lookup and mutation-decoration paths in ticket 03.

## Constraints

- Preserve literal basename-only matching, 700 ms debounce, immediate clear, explicit Enter/command/case-toggle behavior, and workspace-local AND composition with indexed-search and IPTC-empty conditions.
- Preserve selection, active photo, scroll restoration, empty-state feedback, mutation/unverified markers, keyboard navigation, and stale-result correctness.
- Do not add a global path search, SQLite filename query, filesystem rescan, globbing, regular expressions, persisted state, general boolean expressions, or a speculative thread-pool expansion.
