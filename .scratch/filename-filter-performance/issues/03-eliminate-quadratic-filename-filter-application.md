# 03 — Eliminate Quadratic Filename-Filter Application

Status: completed
Priority: high
Category: performance-regression
Milestone: M4 — Faster photo-finding and tagging workflows
Blocked by: 02

## Goal

Make final filename-filter application against a 3,000-path loaded Photo Workspace complete within the 300 ms responsiveness budget without moving filtering or Qt item mutation to a worker.

## Cause and Direction

`PhotoWorkspace.snapshot()` currently recalculates `_filtered_visible()` once per path while deriving its ordered visible tuple. This turns the literal basename predicate into quadratic work. The Qt adapter then repeatedly normalizes already canonical workspace paths while decorating each row and locating the restored selection.

- Derive filtered membership once per snapshot, then order that membership from `_paths`.
- Maintain a canonical path-to-`QListWidgetItem` map as rows are populated and clear it with the Files pane. Use it for active-photo and scroll restoration lookups.
- Treat paths supplied from `PhotoWorkspaceSnapshot` as canonical in row decoration; do not resolve them again before querying mutation or IPTC-verification state. Normalize only at external input boundaries.
- Retain the current synchronous renderer. The controlled profile reaches 0.038 s after only these changes; do not add batching, a worker, or a model-backed view unless the completed implementation fails the budget.

## Acceptance Criteria

- [x] `python3 tests/profile_filename_filter.py` passes: applying the condition to 3,000 loaded paths invokes `_filtered_visible()` no more than twice (selection repair plus snapshot derivation).
- [x] The harness reports one matching path; existing workspace tests retain literal basename, NFC, and case-sensitive behavior.
- [x] A controlled offscreen MainWindow characterization applies a final 3,000-path filename filter within 300 ms on the deterministic fake adapters, including selection, active photo, scroll restoration, and mutation/unverified row decoration.
- [x] File-pane item lookup no longer scans and normalizes every row; map lifecycle is covered across synchronous renders, workspace replacement, and the existing batched-render/stale-cancellation suite.
- [x] No SQLite, filesystem, metadata, preview, or additional background work starts because a filename condition changed.
- [x] Existing filename, indexed-search, IPTC-empty, clear, command, and shortcut regression suites remain green.

## Implementation Notes

- `PhotoWorkspace.snapshot()` now derives visible membership once and preserves display order from `_paths`.
- `MainWindow` indexes rendered items by canonical path, clears that index for every Files-pane rebuild, and cancels queued batch work before a synchronous transition.
- Snapshot rendering passes its canonical paths directly to mutation decoration; external refresh paths retain normalization at the adapter boundary.
- `python3 tests/profile_filename_filter.py` now reports 0.003 s, two derived-membership calls, and one visible path on the 3,000-path fixture. The controlled offscreen final UI application measured 0.043 s.
- The apparent No tags regression was verified as normal asynchronous behavior: its source view remains visible while the indexed query runs; after the checkbox becomes checked, its result is applied. A mixed tagged/untagged offscreen reproduction confirmed only IPTC-empty rows remain visible.

## Validation

- `python3 tests/profile_filename_filter.py`
- `ruff check --no-cache` and `ruff format --check --no-cache` on modified Python files
- `QT_QPA_PLATFORM=offscreen python3 -m unittest discover -s tests -v`
- `git diff --check`

## Constraints

- Preserve literal basename-only matching, the 700 ms debounce, immediate clear, explicit Enter/command/case-toggle behavior, and workspace-local AND composition.
- Keep logical membership in `PhotoWorkspace` and Qt ownership in `MainWindow`.
- Do not add global path search, SQLite filename queries, filesystem scans, globbing, regular expressions, persisted filter state, general boolean expressions, or speculative thread-pool work.
