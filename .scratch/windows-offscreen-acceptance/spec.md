# Windows Offscreen Acceptance

Status: completed

## Problem Statement

Several completed historical tickets record Windows offscreen acceptance as outstanding. The repository targets Windows primarily, while the available agent environment cannot provide that acceptance.

## Desired Outcome

Make the current full offscreen unit suite pass in the Windows project environment, then record the passing result so outstanding historical acceptance notes can be closed with evidence.

## Current Failure

The required command initially failed with 20 failures and 7 errors. After the tracked repairs in `.scratch/platform-neutral-test-fixtures/`, `.scratch/sqlite-connection-lifecycle/`, and `.scratch/main-window-test-storage-isolation/`, the Windows rerun passed all 109 tests.

## Scope

- Activate the Windows project environment with the declared PyQt6 dependency.
- Run `set QT_QPA_PLATFORM=offscreen && python -m unittest discover -s tests -v`.
- Record the command, environment, pass/fail result, and any failures in the issue comments.
- If it passes, update only the historical acceptance notes that explicitly remain open for this run.

## Out of Scope

- Changing production behavior, test semantics, or dependencies solely to obtain a pass.
