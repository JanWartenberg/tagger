# Main Window Dead-Code Cleanup

Status: completed
Priority: low

## Problem Statement

The MainWindow implementation retains unused helper paths and state fields. Dead code obscures the active design and can hide future defects, such as a dormant keyboard helper referring to uninitialized state.

## Solution

Remove verified-unused MainWindow state and helpers while preserving supported controls, commands, shortcuts, and public entrypoints.

## User Stories

1. As a maintainer, I want active behavior to be distinguishable from abandoned implementation paths.
2. As a maintainer, I want unreachable code not to carry invalid assumptions into a future change.
3. As a TAGGER user, I want cleanup to make no observable workflow change.

## Implementation Decisions

- Inventory references before deletion; remove only code with no supported runtime caller.
- Retain documented or externally wired public entrypoints unless an explicit replacement exists.
- Do not combine cleanup with behavior changes or broad formatting.

## Testing Decisions

- Run the complete existing pure and offscreen test suites.
- Add a regression test only if removing code reveals a supported behavior that was previously untested.
- Use static reference search as supporting evidence, not as the sole correctness proof.

## Out of Scope

- Refactoring active MainWindow responsibilities into new modules.
- Reworking the keyboard interaction model.

## Further Notes

This is suitable for direct ticketing after a fresh reference inventory.

## Comments

Completed:

- Removed the unread `_folder_tag_cache` and `_folder_scans_inflight` state, including their workspace-reload resets.
- Removed the unreachable `_ensure_folder_scan(folder, recursive)` helper, which only delegated to the active index-sync path.

Validation completed:

- `rg -n '_folder_tag_cache|_folder_scans_inflight|_ensure_folder_scan' . --glob '*.py'` (no remaining references)
- `ruff check --no-cache .`
- `ruff format --check --no-cache exif_ui.py`
- `python3 -m compileall -q exif_ui.py tests`
- `QT_QPA_PLATFORM=offscreen python3 -m unittest discover -s tests -v` (46 tests)
- `git diff --check`