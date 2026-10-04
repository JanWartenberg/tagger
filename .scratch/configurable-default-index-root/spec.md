# Configurable Default Index Root

Status: completed
Priority: medium

## Goal

Allow users to configure TAGGER's preferred default index root instead of
relying on the built-in `Path.home() / "Pictures"` fallback.

## Current Behavior

TAGGER remembers the last folder selected in `%APPDATA%\tagger\config.json` and
uses it for the next folder dialog. `DEFAULT_INDEX_ROOT` is not an explicit
user setting; it is only a preferred fallback when no existing `.tagger` marker
identifies an index root.

## Scope

- Add a persisted preferred index-root setting.
- Provide a simple UI or command to choose and change it.
- Preserve the existing last-folder behavior separately.
- Keep existing `.tagger` marker discovery authoritative over the preference.
- Handle missing, moved, or invalid configured folders without blocking startup.

## Out of Scope

- Moving photo folders or index databases.
- Changing `.tagger` marker discovery.
- Linux-specific UI or acceptance requirements.

## Acceptance Criteria

- [x] A user can inspect and change the preferred default index root.
- [x] The setting survives restart.
- [x] Existing index-root discovery takes precedence when a marker is present.
- [x] Missing or invalid settings fall back safely.
- [x] Tests cover persistence, precedence, restart behavior, and invalid paths.

## Completion — 2026-10-04

Implemented through `:indexroot` in both application views, with Browse, Save,
Cancel and Restore Defaults. The preference applies only when resolving future
workspace paths contained by that root; existing markers remain authoritative.
See the implementation ticket for automated evidence and platform limits.
