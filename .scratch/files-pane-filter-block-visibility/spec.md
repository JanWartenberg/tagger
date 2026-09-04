# Files-Pane Filter Block Visibility

Status: completed
Priority: medium

## Problem Statement

The Files-pane filter controls consume persistent screen space. TAGGER needs a coherent way to show or hide the whole filter block without making active workspace conditions, keyboard access, or recovery from an empty result undiscoverable.

## Desired Outcome

Define whether and how the Files-pane filter block can be collapsed while preserving the visibility and individual clearing of active Tags/Date, IPTC-empty, filename, and directory-exclusion conditions.

## Recorded Decisions

- The Files-pane filter block starts open on every application launch. Its visibility is session-local presentation state: it is not persisted, and it remains unchanged when the Photo Workspace changes during the same session.
- Put an always-visible compact toggle at the right of the top Files-pane row, after the Add folder control and workspace count. Use Qt standard arrows: down while open and right while collapsed. Its tooltip and accessible name state the available action, `Hide filters` or `Show filters`.
- Expose the same action as `:togglefilters` and the global `Ctrl+Shift+F` shortcut.
- Collapse only the bordered input/action block: Tags, Date, Filename, Exclude folder, Only without IPTC tags, Search, Clear, validation feedback, and any uncommitted drafts. Keep active-condition chips, workspace/result information, loading progress, and empty-result guidance outside it and visible.
- Collapsing is purely visual. Preserve uncommitted field contents and validation state; allow pending filename debounce, search, indexing, and other background operations to continue normally.
- If collapse hides the currently focused filter control, move focus to the Files-pane photo list without changing selection or active photo. `Escape` does not collapse the block and retains each field's existing behavior.
- A command or shortcut that focuses a hidden filter field first opens the block, then focuses and selects that field as usual. Contextual shortcuts inside the filter block need not operate while it is hidden.
- Represent every active Tags, Date, IPTC-empty, Filename, and directory-exclusion condition as a focused, individually removable chip. Tab and Shift+Tab traverse chip buttons; Enter and Space remove the focused condition. After removal, focus the next chip, otherwise the previous chip, and after the last chip the photo list.
- The toggle remains visible at narrow widths. Use Qt's standard arrow rendering and expose its current action to assistive technology rather than relying on a text glyph.
- `MainWindow` owns filter-block visibility. Showing or hiding it never changes Photo Workspace conditions, membership, selection, active photo, or restoration state.

## Constraints

- Preserve the workspace-local AND composition and individual clear behavior of all active Photo Workspace filter conditions.
- Do not hide active conditions, their values, or their removal affordances merely because input controls are collapsed.
- Removing one Tags or Date chip preserves and reapplies the other indexed-search component when present; removing any other chip clears only its represented condition.
- Do not change query grammar, filter matching semantics, SQLite behavior, filesystem discovery, or persisted filter conditions.
- Keep keyboard-driven use fully supported and do not introduce a mouse-only recovery path.
- Do not block the Qt UI thread.

## Completion

The collapsible Files-pane filter block and individually removable active-condition chips were implemented and accepted in `aad1ec8`. Workspace-scoped NoTags querying was subsequently accepted in `7ef8243`.
