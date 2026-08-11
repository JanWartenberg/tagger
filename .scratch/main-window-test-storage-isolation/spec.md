# MainWindow Test Storage Isolation

Status: completed

## Problem Statement

MainWindow characterization tests load persisted recent tags from the user's application storage. Real tags can alter autocomplete candidates, making tests depend on local machine state.

## Desired Outcome

Each MainWindow characterization test starts with deterministic empty persisted state unless it explicitly configures storage data.

## Scope

- Isolate or patch recent-tag and configuration storage at the MainWindow test seam.
- Keep production persistence behavior unchanged.
- Ensure autocomplete assertions see only test-configured values.

## Out of Scope

Changing user storage format, deleting user data, or altering autocomplete behavior.
