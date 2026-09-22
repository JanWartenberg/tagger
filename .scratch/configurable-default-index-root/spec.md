# Configurable Default Index Root

Status: ready-for-agent
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

- [ ] A user can inspect and change the preferred default index root.
- [ ] The setting survives restart.
- [ ] Existing index-root discovery takes precedence when a marker is present.
- [ ] Missing or invalid settings fall back safely.
- [ ] Tests cover persistence, precedence, restart behavior, and invalid paths.
