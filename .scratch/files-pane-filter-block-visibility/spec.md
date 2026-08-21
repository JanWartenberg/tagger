# Files-Pane Filter Block Visibility

Status: needs-triage
Priority: medium

## Problem Statement

The Files-pane filter controls consume persistent screen space. TAGGER needs a coherent way to show or hide the whole filter block without making active workspace conditions, keyboard access, or recovery from an empty result undiscoverable.

## Desired Outcome

Define whether and how the Files-pane filter block can be collapsed while preserving the visibility and individual clearing of active Tags/Date, IPTC-empty, filename, and directory-exclusion conditions.

## Open Triage Decisions

- Define the initial state and whether visibility is session-local, workspace-local, or persisted across application restarts.
- Define the control, label, placement, command vocabulary, and shortcuts for showing and hiding the block.
- Define whether hiding collapses only input controls or also active-condition chips, filter status, and empty-result guidance. Active conditions must remain visible and individually clearable while the block is hidden.
- Define focus transitions: hiding while a child control has focus, showing on a field-focus command, Tab/Shift+Tab traversal, Escape, and keyboard access to active-condition chip removal.
- Define interaction with filter operations, validation guidance, empty states, window resizing, and Files-pane focus restoration.
- Confirm this is presentation state owned by `MainWindow`, not Photo Workspace filter state; hiding the block must never alter active conditions or derived membership.

## Constraints

- Preserve the workspace-local AND composition and individual clear behavior of all active Photo Workspace filter conditions.
- Do not hide active conditions, their values, or their removal affordances merely because input controls are collapsed.
- Do not change query grammar, filter matching semantics, SQLite behavior, filesystem discovery, or persisted filter conditions.
- Keep keyboard-driven use fully supported and do not introduce a mouse-only recovery path.
- Do not block the Qt UI thread.
