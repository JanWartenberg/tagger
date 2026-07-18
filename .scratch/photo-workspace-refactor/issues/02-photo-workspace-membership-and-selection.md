# Introduce PhotoWorkspace for membership and selection

Status: ready-for-agent
Blocked by: 01

## Goal

Introduce the plain-Python `PhotoWorkspace` module and move Photo Workspace identity, insertion order, membership, visible selection, and active-photo rules into it.

## Interface direction

Use one mutable `PhotoWorkspace` object. Its interface accepts intent-level operations (add paths, reload paths, select paths) and exposes immutable rendering snapshots/results. It must not expose mutable internal collections or import Qt.

## Acceptance criteria

- The module lives in the repository's flat module structure and imports no Qt, ExifTool, SQLite, filesystem, or worker code.
- It normalizes identities, preserves insertion order, and ignores duplicate adds.
- Reload clears prior Photo Workspace membership and state before accepting discovered paths.
- Selection is ordered by display order; the first visible selected photo is active.
- A visibility change that hides the active selection chooses the same replacement behavior as the current application; no visible result clears selection.
- `MainWindow` becomes a Qt adapter for membership and selection, while its public-looking entrypoints remain callable.
- Add the pure `unittest` behavior coverage established by ticket 01; the Windows adapter tests remain green.

## Out of scope

- IPTC-empty filtering, search-result restoration, metadata reads, and worker scheduling.
