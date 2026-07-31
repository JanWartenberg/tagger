# File-Pane Open, Copy, and Reveal Actions

Status: ready-for-agent
Priority: high

## Problem Statement

TAGGER's file pane lets users select the active photo for tagging, but it offers no keyboard-driven way to open that photo in the operating system's configured image viewer, copy its file path, or reveal it in the system file explorer.

## Desired Outcome

Add four file-pane actions to the existing action catalogue. Each action must be available as a documented `:` command and a keyboard shortcut while the file pane has focus:

1. **Open** the active photo using the operating system's default application. On the Windows tagging workstation this is expected to be IrfanView through the normal file association; TAGGER must not hard-code an IrfanView executable path.
2. **Open in GIMP** using `C:\Program Files\GIMP 3\bin\gimp-3.exe` on Windows, or a `gimp` executable found on `PATH` on other platforms.
3. **Copy file path** for the active photo to the system clipboard as plain text.
4. **Open in system explorer** by opening the active photo's containing folder and selecting/revealing the photo where the platform supports that behavior.

## User Stories

1. As a keyboard-focused tagger, I want to open the active photo in my configured image tool without leaving TAGGER.
2. As a user, I want to copy the active photo's path for use in another application.
3. As a user, I want to reveal the active photo in Windows Explorer so I can perform file-management work.
4. As a maintainer, I want these actions to appear in the existing command list and follow the same dispatch and shortcut-routing rules as other file-pane actions.

## Proposed Implementation Boundary

- Add one catalogue action for each operation; do not add a parallel shortcut or command-dispatch mechanism. The commands are `:open`, `:opengimp` (with `:gimp` alias), `:copypath`, and `:reveal`.
- Bind the file-pane sequences `Space O`, `Space G`, `Space C`, and `Space R`. Pressing `Space` shows a footer hint for those actions plus the existing `Space Y` and `Space P` routes for 1,000 ms.
- Copy path and Reveal always target the active Photo Workspace path. If there is no active photo, do nothing destructive and use normal non-modal status feedback. Successful copying reports `"<absolute path>" was copied`; Reveal reports `Revealing "<absolute path>" in Explorer…` when initiated.
- Open uses the platform's normal file association. When opening all selected photos, submit each path independently and leave instance behavior to that application.
- Open in GIMP resolves the fixed Windows path first and otherwise resolves `gimp` from `PATH`. It must report a non-modal error if no executable is available. When opening all selected photos, invoke GIMP once with every selected path and reuse an already-running GIMP instance when possible.
- For either Open action with multiple selected photos, show a modal choice with All, active Only, and Cancel; Cancel is the default and Escape behavior.
- On Windows, reveal the selected file in Explorer. On platforms without an equivalent select/reveal interface, open the containing directory using the platform-appropriate launcher.
- Keep OS-process and clipboard details behind focused UI helpers so action handlers remain straightforward and testable.

## Testing Decisions

- Add offscreen MainWindow coverage that invokes each action through the action catalogue, command dispatcher, file-pane shortcut, and context menu as appropriate.
- Assert the active path is passed to mocked OS opener/reveal helpers and that copy writes the expected plain-text path to a test clipboard.
- Cover active-only, all, Cancel, launcher failure, and no-active-photo behavior.
- Assert the four commands are included in the command list and their shortcuts/key routes are registered without displacing existing file-pane controls.
- Cover right-click selection behavior: an unselected photo becomes the sole selection; a selected photo preserves the multi-selection; Ctrl+right-click adds an unselected photo, makes it active, and then opens the menu.
- Manually validate on Windows that the GIMP action opens a multi-photo request in one already-running GIMP instance.

## Triage Decisions

- Copy path and Reveal operate on the active photo only. Both Open actions prompt for All, active Only, or Cancel when multiple photos are selected.
- The file-pane context menu contains only the four new file actions. Right-clicking an unselected photo selects it alone; right-clicking an already selected photo preserves the selection; Ctrl+right-click adds an unselected photo and makes it active.
- Launcher failures and no-active-photo cases use non-modal footer feedback.
- GIMP configuration is intentionally deferred; the fixed Windows path and non-Windows `PATH` fallback are the current contract.

## Out of Scope

- Configuring, bundling, or detecting IrfanView.
- A user-configurable GIMP executable path or support for other named editors.
- Building an internal image viewer or file manager.
- Bulk copying or revealing every selected file.
