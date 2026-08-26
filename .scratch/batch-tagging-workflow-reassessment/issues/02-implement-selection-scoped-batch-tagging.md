# 02 — Implement Selection-Scoped Batch Tagging

Status: completed
Priority: medium
Category: feature
Milestone: M-Future — Unscheduled opportunities
Blocked by: 01

## Goal

When two or more Files-pane photos are selected, replace the right-side single-photo detail with a responsive batch overview. It lets the user add one tag at a time to the unchanged explicit selection and, once a complete canonical-IPTC summary is available, remove a tag shared by every selected photo.

## Product Contract

- The Files pane and its selection interaction do not change: retain Shift+Click, Shift+Arrow, Ctrl+Space, and color-only selection presentation.
- Show the existing single-photo detail for zero or one selected photo. Show the batch overview for two or more selected photos.
- The overview contains: representative-photo stack, selected count, canonical IPTC tags on every selected photo, and canonical IPTC tags on only some selected photos.
- `i` focuses the existing add-tag input. Enter adds its one normalized, autocomplete-enabled tag to every selected photo, clears the input, retains the Files-pane selection, and retains input focus for the next tag.
- Shared tags have a remove affordance. Partially shared tags are informational only. Removing a shared tag targets every currently selected photo.
- Before summary data is complete, show a loading state and disable shared-tag removal. If reads fail or IPTC is unreadable for any target, show an incomplete/error state and make no claim that a tag is shared.
- Existing pending, confirmed, partial-failure, retry, keyword-limit, index-update, and stale-workspace semantics remain authoritative.

## Design

### Batch summary module

Add a Qt-free deep module at `services/batch_tag_summary.py`. Its interface accepts display-ordered selected paths plus complete `KeywordState` facts and returns an immutable summary suitable for rendering:

- selected path count;
- canonical IPTC tags shared by every selected path;
- canonical IPTC tags present on some but not every selected path.

The module owns case-insensitive identity comparison, NFC/keyword normalization, deterministic display spelling/order, and the rule that a missing or IPTC-unreadable state means no complete summary. It uses canonical `IPTC:Keywords` only; it must not treat XMP-only tags as current tag truth. Keep asynchronous reads, Qt objects, and mutation calls outside this module.

### Main-window orchestration

- On a selection transition with at least two selected paths, render the batch overview immediately in loading state.
- Use `_keywords_cache` and `TagMutationCoordinator.metadata_for()` for already-known state. Submit one `Worker(self.exif.read_keywords_many, missing_paths)` for the remaining normalized paths; `ExifTool.read_keywords_many()` already chunks command lines.
- Associate each request with a monotonically increasing batch-summary generation and the exact ordered selection. A completion updates cache/coordinator/index facts, then renders only if both generation and selection still match. A stale completion has no visible effect.
- A newer selection supersedes queued rendering. In-flight ExifTool work need not be forcibly killed, but its result must be ignored when stale. Never perform metadata reads or aggregation on the Qt UI thread.
- If the read fails, reports fewer paths than requested, or any state has `iptc_readable == False`, render incomplete/error summary and keep removal disabled. Preserve any already-rendered batch target count and add-tag capability.
- After a tag-mutation lifecycle event affecting the current selection, recompute the summary from coordinator/cache facts or schedule a fresh missing-state read. Do not show a removed tag as shared after its pending or confirmed state changes.
- Keep the active photo as a Photo Workspace concept. It does not drive batch mutation target or single-photo detail while the batch overview is visible.

## Acceptance Criteria

- [x] A pure-module test covers: all-shared tags, partially shared tags, case/Unicode-equivalent identities, deterministic display spelling/order, empty tags, missing state, and unreadable IPTC state.
- [x] Selecting two or more photos displays the loading batch overview without changing Files-pane selection, controls, or selection semantics; returning to zero/one restores existing detail behavior.
- [x] Cached facts render a complete summary without a metadata read; uncached facts use one background bulk read and never block the Qt event loop.
- [x] A changed selection or replaced Photo Workspace prevents an earlier summary completion from rendering.
- [x] Loading, incomplete, and error states never expose a removable shared tag. A complete summary exposes removals only for tags canonical-IPTC-shared by every current target.
- [x] `i`, autocomplete, Enter, selection retention, input-focus retention, and sequential addition work for a multi-photo selection. The existing one-photo flow remains unchanged.
- [x] Removing a shared tag sends the existing reliable mutation flow to every current selected photo; pending/partial-failure/retry outcomes remain correct and the summary refreshes without stale claims.
- [x] Offscreen tests cover a representative stack/count, shared vs partial tags, loading/error state, stale completion, add, and shared removal.
- [x] No synchronous filesystem, SQLite, ExifTool, or image work is added to selection handling or batch-summary rendering.

## Suggested Test Locations

- `tests/test_batch_tag_summary.py` for the Qt-free summary module.
- `tests/test_main_window_characterization.py` for offscreen selection, focus, worker-generation, loading/error, and mutation integration behavior.

## Validation

- `ruff check --no-cache services/batch_tag_summary.py exif_ui.py tests/test_batch_tag_summary.py tests/test_main_window_characterization.py`
- `ruff format --check --no-cache services/batch_tag_summary.py exif_ui.py tests/test_batch_tag_summary.py tests/test_main_window_characterization.py`
- `QT_QPA_PLATFORM=offscreen python3 -m unittest tests.test_batch_tag_summary tests.test_main_window_characterization -v`
- `git diff --check`

## Constraints

- Do not change `PhotoWorkspace` membership, selection, active-photo, filter, restoration, or Files-pane interaction rules.
- Do not create a second batch-selection model, recursive folder target, hidden-result selection, saved selection, modal confirmation, or general bulk-edit mode.
- Do not use XMP as an alternative tag source; mismatch handling remains the existing single-photo resolution workflow.
- Preserve responsiveness and latest-selection-wins behavior for every asynchronous completion.
