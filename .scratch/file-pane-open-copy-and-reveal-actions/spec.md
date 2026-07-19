# File-Pane Open, Copy, and Reveal Actions

Status: needs-triage
Priority: medium

## Problem Statement

TAGGER's file pane lets users select the active photo for tagging, but it offers no keyboard-driven way to open that photo in the operating system's configured image viewer, copy its file path, or reveal it in the system file explorer.

## Desired Outcome

Add three file-pane actions to the existing action catalogue. Each action must be available as a documented `:` command and a keyboard shortcut while the file pane has focus:

1. **Open** the active photo using the operating system's default application. On the Windows tagging workstation this is expected to be IrfanView through the normal file association; TAGGER must not hard-code an IrfanView executable path.
2. **Copy file path** for the active photo to the system clipboard as plain text.
3. **Open in system explorer** by opening the active photo's containing folder and selecting/revealing the photo where the platform supports that behavior.

## User Stories

1. As a keyboard-focused tagger, I want to open the active photo in my configured image tool without leaving TAGGER.
2. As a user, I want to copy the active photo's path for use in another application.
3. As a user, I want to reveal the active photo in Windows Explorer so I can perform file-management work.
4. As a maintainer, I want these actions to appear in the existing command list and follow the same dispatch and shortcut-routing rules as other file-pane actions.

## Proposed Implementation Boundary

- Add one `ActionSpec` for each action in `actions.py`; do not add a parallel shortcut or command-dispatch mechanism.
- Define explicit command names and non-conflicting file-pane shortcut/key-route bindings during triage. The commands should be discoverable through `:listcommands` and command-line completion.
- Resolve the target from the active Photo Workspace path. If there is no active photo, do nothing destructive and give normal status feedback.
- Use the platform's normal file association to open a photo. IrfanView remains a user-managed Windows association, not a TAGGER dependency or configuration setting.
- On Windows, reveal the selected file in Explorer. On platforms without an equivalent select/reveal interface, open the containing directory using the platform-appropriate launcher.
- Keep OS-process and clipboard details behind small MainWindow helpers so action handlers remain straightforward and testable.

## Testing Decisions

- Add offscreen MainWindow coverage that invokes each action through the action catalogue or command dispatcher.
- Assert the active path is passed to a mocked OS opener/reveal helper and that copy writes the expected plain-text path to a test clipboard.
- Cover the no-active-photo path for all three actions.
- Assert the three commands are included in the command list and their shortcuts/key routes are registered without displacing existing file-pane controls.

## Open Triage Decisions

- Choose the final command names, aliases, and shortcuts after checking action-catalogue conflicts.
- Confirm whether actions always operate on the active photo (recommended) or define explicit multi-selection semantics.
- Confirm the desired user-facing status/error wording when the OS launcher fails.

## Out of Scope

- Configuring, bundling, or detecting IrfanView.
- Building an internal image viewer or file manager.
- Bulk opening, copying, or revealing every selected file unless explicitly selected during triage.
