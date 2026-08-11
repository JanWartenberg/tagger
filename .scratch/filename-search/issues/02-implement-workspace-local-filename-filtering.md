# 02 — Implement Workspace-Local Filename Filtering

Status: completed
Category: enhancement
Priority: medium
Milestone: M4 — Faster photo-finding and tagging workflows
Blocked by: None

## Goal

Deliver the approved workspace-local filename filter while preserving TAGGER's coherent Photo Workspace ownership, active-filter transparency, and keyboard-driven workflow.

## Scope

- Add one optional filename condition to the Qt-free Photo Workspace seam. Derive visible membership by applying it to the complete current source after any indexed-search and IPTC-empty source calculation; do not model it as a competing view mode or parallel `MainWindow` state.
- Match NFC-normalized complete basenames, including extensions, with literal trimmed substring semantics. Default to case-folded matching; support case-sensitive matching through the condition's `Aa` state.
- Preserve source membership beneath the condition so individual clearing restores the current underlying indexed-search/IPTC-empty/folder result rather than a filename-filtered subset.
- Apply the condition to incoming discovery and drag/drop paths. Replacing the Photo Workspace resets the query and case mode.
- Add the dedicated **Filter filenames** field, `Aa` toggle, `Ctrl+F`, contextual `Alt+F`, `:focusfilenamefilter`, `:filterfiles <query>`, `:filterfiles --case <query>`, `:clearfilenamefilter`, and `:clearfilters` through the action catalogue.
- Make edits live; Enter focuses the first visible photo; Escape leaves the condition active and returns focus. Empty field text removes only this condition.
- The later Files-pane filter UI redesign groups Filename with separate Tags and Date inputs; it does not change filename-filter ownership or semantics.
- Keep `:clearsearch`, `:clear`, and `:back` limited to indexed-search clearing.
- Render active conditions as compact chips with match/progress feedback in the Files pane. Render the centred generic empty state for every zero-result filter/search combination.

## Acceptance Criteria

- [x] Filename matching uses only the basename, includes extensions, trims outer whitespace, treats query punctuation literally, handles NFC equivalence, and is case-insensitive by default.
- [x] The `Aa` toggle and `--case` command option produce case-sensitive matching; both controls visibly reflect the active mode.
- [x] Filename, IPTC-empty, and indexed-search conditions combine as AND. Activating or clearing one recomputes from its complete natural source and retains every other condition.
- [x] An empty intersection has no selected or active photo and displays `No photos match the active filters.` centred in the files pane.
- [x] Starting/clearing a filename condition repairs selection and restores the captured source selection and scroll anchor according to the approved workflow; stale async indexed/IPTC completions cannot overwrite the current derived view.
- [x] New workspace paths are included only if they satisfy active conditions; a replaced workspace clears filename state and resets case mode.
- [x] Each individual clear affects only its named condition; `:clearfilters` atomically restores the folder view.
- [x] Keyboard focus, Enter, Escape, command routing, field/toggle state, and the multi-condition indicator are covered by offscreen tests.
- [x] Pure Photo Workspace tests cover composition, source changes, empty intersections, lifecycle, and restoration without Qt, SQLite, filesystem, or ExifTool dependencies.

## Completion

Implemented with live workspace filtering, composable indexed-search/IPTC-empty conditions, commands, empty-state feedback, and pure/offscreen regression coverage.

## Constraints

- Do not add a SQLite filename query, filesystem traversal, metadata read, directory/full-path matching, `file:` indexed-search syntax, OR/NOT composition, globbing, or regular expressions.
- Keep logical membership, condition state, selection repair, and restoration in `PhotoWorkspace`; keep Qt rendering, widget focus, controls, and pixel scroll handling in `MainWindow`.
- Do not regress current indexed-search, IPTC-empty, explicit-refresh, stale-result, and command behavior.

## Validation

- `ruff check actions.py exif_ui.py photo_workspace.py services tests`
- `ruff format --check actions.py exif_ui.py photo_workspace.py services tests`
- `QT_QPA_PLATFORM=offscreen python3 -m unittest discover -s tests -v`
- `git diff --check`
