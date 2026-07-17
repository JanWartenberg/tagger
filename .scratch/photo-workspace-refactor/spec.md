# Photo Workspace Refactor

Status: ready-for-agent

## Problem Statement

TAGGER's photo-files pane is controlled by state and behavior spread throughout the main window. Loaded paths, visibility, selection, IPTC-empty filtering, database-search matches, asynchronous progress, stale-result rejection, and view restoration are coupled directly to Qt widgets. This makes changes risky, forces maintainers to reason across unrelated UI code, and leaves important behavior difficult to test without running the application.

The current application is authoritative. The indexing plan describes an incomplete future state and must not be interpreted as current behavior during this refactor.

## Solution

Introduce a deep Photo Workspace module as the plain-Python data model backing the photo-files pane. It will own photo membership, ordering, view state, visibility, selection, filter progress, and stale-result rules. The main window will become a thin Qt adapter that forwards user intent, schedules background work, and renders workspace state.

All observable behavior and stable outside interfaces remain unchanged. The refactor creates a testable seam for later search, filtering, and multi-photo improvements without implementing those improvements now.

## User Stories

1. As a TAGGER user, I want the application to launch exactly as before, so that the refactor does not disrupt my workflow.
2. As a TAGGER user, I want the photo-files pane to show the same photos in the same order, so that navigation remains familiar.
3. As a TAGGER user, I want duplicate photo paths to remain suppressed, so that adding the same photo twice does not clutter the workspace.
4. As a TAGGER user, I want folder loading to retain its current behavior, so that opening a folder produces the same workspace as before.
5. As a TAGGER user, I want drag-and-drop to retain its current behavior, so that I can continue adding photos naturally.
6. As a TAGGER user, I want multi-selection to behave exactly as before, so that bulk tagging is not affected.
7. As a TAGGER user, I want the earliest selected photo in display order to remain the active photo, so that preview and metadata behavior do not change.
8. As a TAGGER user, I want keyboard navigation and pane focus behavior to remain unchanged, so that the keyboard-driven workflow stays intact.
9. As a TAGGER user, I want the IPTC-empty filter to produce the same progressive results as before, so that the refactor does not alter the working list.
10. As a TAGGER user, I want a newly tagged photo to retain the current one-step visibility behavior under the IPTC-empty filter, so that tags can still be copied to the next photo.
11. As a TAGGER user, I want stale background filter results to be ignored, so that old work cannot overwrite my current view.
12. As a TAGGER user, I want filter failures to leave the last successful view intact, so that an error does not destroy my workspace state.
13. As a TAGGER user, I want database-search matches to affect currently loaded photos exactly as before, so that existing search behavior is preserved.
14. As a TAGGER user, I want clearing database search to restore visibility using current behavior, so that clearing a query remains predictable.
15. As a TAGGER user, I want selection to move to the same visible photo when filtering hides the active selection, so that navigation remains usable.
16. As a TAGGER user, I want an empty filtered result to clear selection as before, so that hidden photos are not treated as active.
17. As a TAGGER user, I want scroll position and viewport anchoring preserved while visibility changes, so that the pane does not jump unexpectedly.
18. As a TAGGER user, I want long-running metadata work to remain in background threads, so that the interface stays responsive.
19. As a TAGGER user, I want status and error feedback to remain materially unchanged, so that background work remains understandable.
20. As a TAGGER user, I want configuration, recent tags, index data, and photo metadata formats to remain unchanged, so that existing local data continues to work.
21. As a Windows user, I want TAGGER to retain its current Windows behavior, so that my primary environment remains supported.
22. As a Linux user, I want the internal model to remain platform-independent, so that Linux compatibility remains practical.
23. As a maintainer, I want photo-files pane rules concentrated in one module, so that behavior changes have locality.
24. As a maintainer, I want to test workspace behavior without constructing Qt widgets, so that tests are fast and deterministic.
25. As a maintainer, I want asynchronous result acceptance rules tested independently from thread mechanics, so that race-condition regressions are easier to prevent.
26. As a maintainer, I want Qt-specific rendering and focus behavior kept outside the workspace, so that the model remains reusable and understandable.
27. As a maintainer, I want existing main-window entrypoints and public adapter methods preserved, so that callers and signal wiring do not break.
28. As a maintainer, I want the migration performed in small verified steps, so that structural mistakes are detected early.
29. As a maintainer, I want unrelated legacy code left untouched, so that review remains focused on the workspace refactor.
30. As a future maintainer, I want later filter and search changes to be localized behind the Photo Workspace seam, so that extending TAGGER does not require another main-window-wide rewrite.

## Implementation Decisions

- **Photo Workspace definition:** The Photo Workspace is the application data model backing the photo-files pane. It is not a Qt widget model and contains no rendering implementation.
- **Module shape:** Use one mutable `PhotoWorkspace` object with encapsulated state and intent-based operations. Expose read-only snapshots or results for rendering rather than public mutable collections.
- **Module placement:** Keep the module in the repository's existing flat Python module structure. Do not introduce a package hierarchy as part of this work.
- **Workspace ownership:** The workspace owns loaded photo identities, insertion order, active view mode, per-photo visibility, ordered selection, the active photo rule, logical restoration state, filter progress, pending filter batches, and stale-result acceptance.
- **Metadata ownership:** The workspace does not own complete metadata records, EXIF dates, or tag contents. It accepts only facts required to determine pane state, such as whether a photo is IPTC-empty.
- **Photo identity:** Continue using normalized absolute path strings. Preserve insertion order, and treat adding an existing path as a no-op.
- **Active photo:** Order selection by workspace display order. The first visible selected photo remains the active photo for preview and metadata, matching current behavior.
- **Qt adapter:** The main window forwards widget events to the workspace, schedules background operations, and renders workspace results. Filtering, mode, selection, restoration, and stale-result rules must not be duplicated in Qt code.
- **Qt-owned state:** Focus, scrollbar values, pixel offsets, viewport anchoring, workers, thread-pool use, timers, signal wiring, and dialogs remain in the Qt implementation.
- **Asynchronous filtering:** The workspace owns logical progress, pending batches, and operation identity. Background execution remains outside. Every result passes through the workspace before rendering, and stale results are ignored.
- **Failure behavior:** A failed metadata-filter batch leaves the last successfully rendered membership, selection, and visibility intact. Existing Qt status and error reporting remains responsible for notifying the user.
- **IPTC-empty behavior:** Preserve the current one-step exception for newly tagged photos. Do not replace it with frozen-snapshot behavior during this refactor.
- **Database search:** Query parsing, SQLite access, and execution remain outside. The workspace receives matching photo identities and applies them only to currently loaded photos using current behavior.
- **Folder and drop input:** Qt and filesystem code discover supported image paths. The workspace accepts normalized paths, deduplicates them, preserves insertion order, and controls resulting selection.
- **Reload behavior:** A folder reload clears workspace state before adding discovered paths. Last-folder persistence and index scheduling remain outside.
- **Stable outside interfaces:** Preserve the launcher, main-window class, UI entrypoint, visible controls and layout, mouse behavior, drag-and-drop, keyboard behavior, command behavior, persisted formats, and materially equivalent status/error behavior.
- **Main-window methods:** Existing public-looking methods used by Qt wiring remain available as thin adapter methods. Underscore-prefixed fields and methods are internal and may move or disappear.
- **Behavior authority:** Current executable behavior is the sole behavior baseline. Future-state planning documents do not override it.
- **Migration order:** First characterize behavior; then introduce the workspace; then move membership and selection; then filtering and stale-result handling; then database-search visibility; finally remove superseded main-window state and rules.
- **Responsiveness:** Potentially long-running metadata and filesystem operations must remain off the UI thread. Plain in-memory workspace transitions may run synchronously.
- **Code standards:** Follow repository guidance, including Ruff for new or modified code, without broadly reformatting unrelated legacy code.

## Testing Decisions

- The primary test seam is the Photo Workspace interface. Tests exercise intent-based operations and assert externally visible snapshots or results, not internal fields or helper methods.
- Workspace tests use Python's built-in `unittest` and run without PyQt, ExifTool, SQLite, real photos, or background threads.
- Characterization tests cover path normalization assumptions, insertion order, duplicate suppression, reload clearing, ordered multi-selection, active-photo choice, visibility, empty results, one-step IPTC-empty preservation, filter progress, stale batch rejection, search-match application, search clearing, and failure preservation.
- Async tests model operation identities and result order directly. They do not use sleeps or real threads.
- A small Qt integration suite verifies the adapter at the highest practical seam: widget events reach the workspace, workspace state is rendered into the files pane, hidden selection is corrected, and existing public main-window methods remain callable.
- Qt tests run offscreen in the normal Windows development environment. They use fakes for metadata and indexing dependencies and must not invoke real ExifTool or touch a user's photo library.
- Pure workspace tests must pass in the Linux agent environment. Qt integration tests must pass on Windows before the refactor is considered complete.
- There is no existing test suite to copy. New tests establish the repository's first characterization-test conventions while avoiding a new runtime dependency solely for testing.
- Do not write pixel-perfect layout tests. Scroll tests assert preserved logical anchoring or stable selection; Qt integration checks only the minimum physical behavior required to prove adapter wiring.
- Each migration slice keeps all existing tests green before the next responsibility moves.

## Out of Scope

- Completing or correcting the indexing plan
- Changing database-search semantics or query syntax
- Implementing frozen-snapshot IPTC-empty filtering
- Fixing unrelated existing bugs
- Restructuring tag mutation behavior
- Restructuring action, shortcut, or command dispatch
- Changing visible layout, controls, labels, shortcuts, or commands
- Changing metadata, configuration, recent-tag, index, or backup formats
- Introducing a new photo identity type or sorting policy
- Introducing a package hierarchy
- Broad formatting or lint cleanup
- Adding security, compliance, tenancy, or remote-data features for this local personal tool

## Further Notes

- Frozen-snapshot IPTC-empty filtering is recorded as deferred follow-up work. Activating that future behavior would capture the photos that are empty at activation time and keep the resulting list fixed until the filter is reapplied.
- The architecture review also identified tag mutation, indexing, and action dispatch as later deepening opportunities. They are intentionally independent from this refactor.
- The environment used for agent work has Python but not PyQt or pytest; the repository's checked-in virtual environment is Windows-specific. This is why the pure model test seam is mandatory and Qt acceptance remains a Windows step.
