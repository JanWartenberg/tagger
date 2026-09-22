# 01 — Add Configurable Default Index Root

Status: ready-for-agent
Category: feature
Priority: medium
Milestone: M-Future — Unscheduled opportunities
Blocked by: None

## Goal

Let users configure TAGGER's preferred default index root rather than relying
on `Path.home() / "Pictures"`.

## Current Behavior

TAGGER persists the last folder selected in `%APPDATA%\tagger\config.json`, but
there is no explicit setting for the preferred default index root. The built-in
default is used only as a fallback when no `.tagger` marker identifies an
index root.

## Scope

- Persist a preferred default index root.
- Add a simple UI or command to choose and change it.
- Keep the preferred root separate from the last folder dialog location.
- Preserve `.tagger` marker discovery as authoritative.
- Fall back safely when the configured folder is missing or invalid.

## Acceptance Criteria

- [ ] A user can inspect and change the preferred default index root.
- [ ] The setting survives restart.
- [ ] Existing marker-based index discovery takes precedence.
- [ ] Missing or invalid settings do not block startup.
- [ ] Tests cover persistence, precedence, restart behavior, and invalid paths.

## Out of Scope

- Moving photo folders or index databases.
- Changing `.tagger` marker discovery.
- Linux-specific UI or acceptance requirements.
