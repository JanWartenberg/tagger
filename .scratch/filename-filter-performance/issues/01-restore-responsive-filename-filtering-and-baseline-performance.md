# 01 — Restore Responsive Filename Filtering and Baseline Performance

Status: needs-triage
Priority: high
Category: performance-regression
Milestone: M4 — Faster photo-finding and tagging workflows
Blocked by: None

## Goal

Remove the roughly 30-second UI freeze caused by typing in **Filter filenames**, then use measurements to identify any separate interactive performance regressions.

## Scope

- Debounce live filename-condition application until the input has been unchanged for 700 ms. Cancelling or replacing a pending request must be immediate; ordinary typing must not synchronously filter or rerender the workspace.
- Apply the completed filename query only to the current complete Photo Workspace source after active indexed-search and IPTC-empty conditions. It must not broaden the result scope or trigger SQLite, filesystem, metadata, or preview work.
- Before selecting an asynchronous implementation, create a deterministic timing harness with a representative large workspace and record time spent in filtering/snapshot derivation, Qt rendering, and event-loop work.
- Decide from that evidence whether condition evaluation and/or rendering must use a non-blocking latest-result-wins workflow. If so, preserve all existing stale-result, selection, active-photo, restoration, and filter-composition rules.
- Capture a repeatable baseline for large workspace rendering, indexed-search result rendering, IPTC-empty filtering, metadata loading, and preview loading. Split measured work beyond this filename-filter fix into independently scoped tickets.

## Acceptance Criteria

- [ ] A deterministic agent-runnable regression test or benchmark reproduces the pre-fix input-latency failure on a large workspace and asserts a documented responsiveness budget after the change.
- [ ] Rapid edits produce no filtering/list-rendering work until 700 ms after the most recent edit; only the final query is applied.
- [ ] Filtering evaluates only the current workspace source and remains a literal basename-only condition with existing NFC and case behavior.
- [ ] The UI event loop remains responsive while entering and replacing filename queries; stale delayed or background results cannot overwrite a newer query or workspace state.
- [ ] Date/tag indexed search, IPTC-empty, filename composition, empty states, clear behavior, selection, restoration, commands, shortcuts, and current background-coordinator behavior remain covered by regression tests.
- [ ] A checked-in or documented repeatable performance baseline distinguishes this problem from other interactive paths and records follow-up tickets only for measured issues.

## Constraints

- Keep logical conditions and derived membership under `PhotoWorkspace`; keep Qt timer, rendering, and input concerns in `MainWindow`.
- Do not introduce a global path search, SQLite filename query, filesystem rescans, globbing, regular expressions, persisted filter state, general boolean expressions, or a speculative thread-pool expansion.

## Comments

- Maintainer reproduction: **Only without IPTC tags** alone is sufficient to make general interaction—not only filename entry—very slow: changing the active photo and typing both lag. A Date-only filter remains responsive. `Clear` restores responsiveness immediately. Treat the IPTC-empty filter state as the first performance-reproduction scenario; do not assume the filename field or Date condition is the cause.
- Initial analysis: an offscreen 3,000-path reproduction has a red 300 ms response-budget assertion. Selecting another visible photo takes 4.63 s with IPTC-empty active and 0.003 s with no IPTC-empty condition. Temporarily bypassing only the IPTC-empty selection path's `_render_photo_workspace()` call reduces it to 0.021 s. `on_selection_changed()` currently takes that path only for `PhotoWorkspaceViewMode.IPTC_EMPTY`, where `_render_photo_workspace()` clears and rebuilds every `QListWidgetItem` synchronously. This is the confirmed direct cause of the selection freeze.
- The same harness measures filename input at 0.40 s for 100 paths, 1.43 s for 300, 3.84 s for 600, and 16.40 s for 3,000 without IPTC-empty; the IPTC-empty state has comparable timings. `apply_filename_filter()` also synchronously invokes the full-list renderer. Debouncing prevents repeated work while typing but does not make the eventual full render responsive; separately measure and replace/coalesce the rendering strategy.
- Partial implementation: selection changes no longer rebuild the Files pane in the IPTC-empty view, and non-empty filename edits now debounce for 700 ms. An explicit filename command, case-mode toggle, Enter, empty-field clear, workspace replacement, and clear-all cancel or commit pending work as appropriate. Offscreen characterization tests cover the debounce and the absent IPTC-empty selection rebuild.
- Maintainer validation: the IPTC-empty/no-tags filter is responsive again after this change. Applying the eventual debounced filename filter against an original folder of roughly 3,000 files still freezes the application. Follow-up investigation is tracked in 02; do not treat debounce as a complete filename-rendering fix.
