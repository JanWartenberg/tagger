# 01 — Add Configurable Default Index Root

Status: completed
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

- [x] A user can inspect and change the preferred default index root.
- [x] The setting survives restart.
- [x] Existing marker-based index discovery takes precedence.
- [x] Missing or invalid settings do not block startup.
- [x] Tests cover persistence, precedence, restart behavior, and invalid paths.

## Out of Scope

- Moving photo folders or index databases.
- Changing `.tagger` marker discovery.
- Linux-specific UI or acceptance requirements.

## Completion — 2026-10-04

- `:indexroot` opens the preference dialog from both views. Browse chooses an
  existing directory; Save persists `default_index_root` separately from
  `last_folder`; Restore Defaults removes the preference when saved.
- Invalid, relative, missing or non-directory preferences fall back to the
  built-in Pictures root. Existing `.tagger` discovery and containment rules are
  unchanged. Saving does not migrate indexes or replace the active root.
- Save errors remain visible in the dialog; Cancel preserves saved settings.
- Passed: 11 focused pytest cases using public command dispatch and Qt controls,
  isolated real config files, reconstructed windows and production root resolution.
  Includes Unicode paths, unrelated config preservation, marker precedence,
  outside-root paths, invalid/removed roots, reset, cancellation and save failure.
- Passed: Ruff check/format, full offscreen pytest (355 passed, four Windows
  skips, 33 subtests), and portable real-file regression (ten phases, 28 cases).
  Inspected report: `tests/acceptance/reports/20261004T174041.175361Z/report.json`.
- Maintainer accepted the change after confirming `:indexroot` opens the dialog
  and allows choosing a folder. This is maintainer-reported UI evidence.
- Unrun: native Windows automated execution and broader dialog scaling checks.
  Linux results do not validate Windows sharing locks or process cleanup; those
  unchanged checks retain their previous acceptance. No checks waived here.
- Commit authorized by the maintainer; implementation and acceptance notes are
  included together.
