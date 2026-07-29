# 01 — Add File-Pane Open, Copy, and Reveal Actions

Status: needs-triage
Category: feature
Priority: medium
Blocked by: None

## Goal

Add catalogue-backed file-pane actions to open the active photo, copy its path, and reveal it in the platform file explorer.

## Proposed Scope

- Add one `ActionSpec` per action and use existing command, completion, and shortcut routing.
- Resolve the target from the active Photo Workspace path.
- Keep platform launching and clipboard access behind focused MainWindow helpers.
- Cover active and no-active-photo behavior through offscreen tests.

## Required Triage Before Implementation

- Final command names, aliases, and non-conflicting file-pane shortcuts.
- Active-photo-only versus explicit multi-selection semantics.
- User-facing launcher failure and no-active-photo feedback.

## Comments

Created to make the existing feature spec trackable. See `../spec.md` for platform and testing constraints.
