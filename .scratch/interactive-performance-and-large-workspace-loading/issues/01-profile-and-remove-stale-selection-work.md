# 01 — Profile and Remove Stale Selection Work

Status: completed
Category: bug
Priority: high
Blocked by: None

## Goal

Make the last photo selected during rapid keyboard navigation responsive without waiting for obsolete metadata work started for earlier selections.

## Acceptance Criteria

- [x] The existing rapid-selection regression test passes: with one worker, six rapid selection changes, and 100 ms reads, metadata for the final selection is rendered in under 300 ms.
- [x] Obsolete selection work cannot delay the latest selection behind the serial worker queue.
- [x] A stale completion cannot render metadata, preview, or status for a no-longer-selected photo.
- [x] The fix preserves non-blocking UI acknowledgement and existing selection behavior.
- [x] The full offscreen suite, Ruff, formatting, and `git diff --check` pass.

## Original Reproduction (fixed)

Run:

```bash
QT_QPA_PLATFORM=offscreen python3 -m unittest \
  tests.test_main_window_characterization.MainWindowCharacterizationTests.test_latest_selection_is_not_delayed_by_stale_metadata_reads -v
```

Before the fix, the final selection took approximately 0.66 seconds and failed the 0.3-second budget. The test is intentionally minimized to six quick changes; the observed user workflow usually involves 20–30 changes and could take seconds.

## Resolution

`MainWindow.on_selection_changed()` starts a new worker for every selection. `_selection_token` suppresses stale rendering only after each `ExifTool.read_keywords()` call has already run. With constrained or busy workers, obsolete reads fill the queue and the final selection waits for them.

Implemented: a latest-selection-wins/coalescing seam replaces per-selection FIFO submission, allowing the final selection to pass the regression test without making individual ExifTool reads faster.

## Follow-up Work

1. Stale preview work shared the global Qt thread pool. Completed: preview loading is debounced and stale queued preview workers are discarded.
2. Discovery of a 29,821-photo folder returns only after the complete traversal. Rejected for this feature.
3. A `date:2025` search returning 2,910 results takes about five seconds. Rejected for this feature.

## User Observations

- Around 1,200 loaded photos: broadly acceptable.
- 29,821 loaded photos: roughly 20 seconds before the workspace is available.
- `date:2025`, 2,910 results: roughly five seconds.
- Working on the resulting 2,900-photo subset is broadly acceptable.

## Comments

Created before product-ticket triage because interaction latency was a P0 usability issue. The regression and its first hypothesis are now resolved; the remaining follow-up work is recorded above.

Implemented a latest-selection-wins metadata-read seam in `MainWindow`: selection changes replace one pending read, a 25 ms owned Qt timer coalesces rapid changes, and only one read can be in flight. Selection clearing invalidates pending metadata and preview work. Metadata completion also preserves newer status feedback rather than replacing it with `Ready`.

Most recent Linux validation on the current `HEAD` passed:

- `QT_QPA_PLATFORM=offscreen python3 -m unittest discover -s tests -v` (113 tests)
- `ruff check exif_ui.py tests/test_main_window_characterization.py`
- `ruff format --check exif_ui.py tests/test_main_window_characterization.py`
- `python3 -m compileall -q exif_ui.py tests/test_main_window_characterization.py`
- `git diff --check`

Windows live acceptance confirmed that scrolling is responsive and behaves as expected. This closes the ticket. The user explicitly declined further investigation of 20,000+ photo loading, discovery progress, and large-search timing for this feature.
