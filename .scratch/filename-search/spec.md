# Filename Search Within the Photo Workspace

Status: completed
Priority: medium

## Problem Statement

TAGGER can search indexed tags and capture dates, but it cannot narrow the current Photo Workspace by filename. Users need to find photos such as names containing `DSC` without replacing their current workspace with an index-wide result.

## Desired Outcome

Provide a visible, keyboard-accessible filename filter that narrows the current Photo Workspace by basename. It is a local, live filter condition: it combines with other active conditions using logical AND and never adds photos from outside the current Photo Workspace.

## Resolved Scope

### Surface and commands

- Add a dedicated visible field labelled **Filter filenames**. It is distinct from the indexed **Tags** and **Date** inputs; `file:` is not added to indexed-search syntax.
- Add a visible `Aa` toggle beside the field. It is off by default for case-insensitive matching.
- Add `Ctrl+F`, `Alt+F` within the Files filter box, and `:focusfilenamefilter` to focus the field and select its text.
- Add `:filterfiles <query>` to set the condition. `:filterfiles --case <query>` sets the condition with case-sensitive matching.
- Add `:clearfilenamefilter` to remove only this condition, and `:clearfilters` to atomically clear every active condition and return to the folder view.
- Existing `:clearsearch`, `:clear`, and `:back` remain indexed-search-only; they do not clear the filename or IPTC-empty conditions.

### Matching and interaction

- Match the complete basename, including its extension; never match parent directories or full paths.
- Normalize the query and basename to Unicode NFC. Default matching is case-folded substring matching; `Aa` matching preserves case after NFC normalization.
- Trim outer query whitespace. All remaining characters, including spaces, `.`, `*`, `?`, and brackets, are literal; glob and regular-expression syntax are out of scope.
- Apply a non-empty condition 700 ms after the most recent edit. An empty field removes the condition immediately.
- Enter commits any pending condition and moves focus to the first visible photo. Escape follows normal line-edit behavior: it leaves the condition intact and only returns focus.
- The query and `Aa` state are session-only. Replacing the Photo Workspace through folder opening or drop clears the query and resets `Aa` to its default.

### Composition and state

- Filename filtering is an independent Photo Workspace condition. Active conditions combine with logical AND.
- It must remain active when the user starts, clears, or refreshes an indexed-search or IPTC-empty condition. Each changed condition computes from its complete natural source, then the filename condition is applied; it must not be limited to the subset previously visible through filename filtering.
- Clearing one condition removes only that condition and immediately reapplies every remaining condition. `:clearfilters` is the sole clear-all operation.
- A filename condition may narrow folder membership, indexed-search results, IPTC-empty results, or their supported combinations. It never schedules SQLite, filesystem, or metadata work.
- Incoming Photo Workspace paths from discovery or drag/drop are evaluated against every active condition before becoming visible.
- Starting the filename condition captures the prior logical visible view, selection, active photo, and Qt scroll anchor. If it hides the active photo, select the first visible match. Clearing it restores that captured context when its source remains current.
- An empty intersection is a real active view. Show a horizontally and vertically centred empty state in the files pane: **No photos match the active filters.** Do not use a list item that could be mistaken for a filename.

### Presentation

- The Files pane shows active conditions as compact chips with a match count; pending indexed-search and IPTC-empty work shows concise progress feedback instead.
- Show the workspace count separately and hide the summary when no condition is active rather than repeating inactive folder-state text.
- The dedicated filename field, checked IPTC-empty control, indexed Tags/Date inputs, and active-filter presentation must agree about which conditions are active.

## Architecture Direction

Keep the Photo Workspace as the sole owner of logical source membership, active filter conditions, derived visibility, selection repair, and restoration. Qt owns widget rendering and physical scroll anchors. Extend the Qt-free seam with one optional filename condition and a derived visibility path; do not introduce a general boolean-expression engine, OR combinations, regexes, or a new SQLite query type.

The existing `PhotoWorkspaceViewMode` continues to describe the underlying source/result mode. Filename filtering is a condition layered on that source, not a competing view mode. Design the condition seam so additional AND conditions can be added later without reintroducing parallel filtering state in `MainWindow`.

## Validation

- Add pure Photo Workspace tests for literal/NFC/case behavior, extension matching, debounced narrowing at the Qt adapter, empty intersections, selection and restoration, source changes beneath an active filename condition, discovery additions, individual clears, and clear-all.
- Add offscreen MainWindow coverage for the dedicated control, `Aa`, commands, shortcut, Enter/Escape behavior, indicator wrapping, centred empty state, and composition with indexed-search and IPTC-empty conditions.
- Preserve existing indexed-search, IPTC-empty, stale-completion, selection, and scroll-restoration behavior.

## Out of Scope

- Directory-name or full-path searching.
- Searching filenames outside the current Photo Workspace.
- `file:` syntax in indexed search.
- OR/NOT combinations, general query composition, globbing, regular expressions, saved filters, or persisted filter state.
- Changing indexed tag/date query semantics, SQLite schema, or background scheduling.
