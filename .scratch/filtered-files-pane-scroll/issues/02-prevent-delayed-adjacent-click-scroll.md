# 02 — Prevent delayed scrolling after an adjacent photo click

Status: completed
Priority: high
Category: bug
Blocked by: None

## Scope

Keep a stable Photo Workspace viewport when the user clicks an already visible
adjacent photo, including No tags results with hidden rows and long paths.
Retain explicit scrolling, keyboard navigation and filter restoration.

## Reproduction and TDD

Test seam: the existing MainWindow Qt adapter, using public mouse events and
observable selection, item geometry and scrollbar values. No personal photos,
desktop input or production index are used by the characterization tests.

- The earlier 10 ms injected-scroll experiment demonstrated a timing gap but
  did not establish the actual trigger. A subsequent native Qt reproduction
  needs no injected events: hide the first 80 of 200 rows, use horizontally
  overflowing paths, select row 100, scroll it to the top, click adjacent row
  101, and wait beyond `QApplication.doubleClickInterval() + 100` milliseconds.
- `test_no_tags_adjacent_click_preserves_scroll_after_native_delay` failed before
  the fix: selected photo remained 101, scrollbar changed from 20 to 79.
- Qt's mouse-press implementation starts a delayed `scrollTo` after its
  double-click window. With overflowing paths, the per-item scroll calculation
  recomputes a vertical position using hidden rows even when the photo is already
  vertically visible. The previous 1 ms restoration runs before this timer.
- Switching the Files pane to pixel scrolling makes the native regression pass
  without extending the restoration timer or suppressing user scroll actions.

## Verification

- Implemented pixel scrolling and corrected the sign of partially clipped
  top-row offsets in both click restoration and workspace rendering.
- TDD: the native adjacent-click test failed at scrollbar 79 versus 20 before
  the mode change. Separate click and matching-filename-filter tests failed at
  1393 versus 1407 before their respective offset corrections. All three pass.
- `ruff check .` passed. Changed Python ranges/files pass Ruff formatting;
  unrelated legacy formatting was preserved.
- Full Linux offscreen pytest: **424 passed, four Windows-only skips,
  33 subtests passed**. The focused scroll/navigation set also passed.
- Real-file acceptance independently inspected:
  `tests/acceptance/reports/20261018T155311.799843Z/report.json`, **18 phases /
  48 cases**, both backup settings, zero child exit codes, verified process
  cleanup and temporary-workspace removal, matching harness hashes. New native
  scroll cases pass with real JPEGs, production indexing/ExifTool and public Qt
  interactions. Navigation, explicit scrolling and unchanged JPEGs are checked.
- First independent review round: two read-only reviewers found no functional
  issues; both independently passed the three new Qt tests. One stale timer
  comment was clarified. Two fresh final reviewers returned no findings; the
  validation reviewer independently passed the three new Qt tests again.
- Windows acceptance was run by the maintainer and its report independently
  inspected: `tests/acceptance/reports/20261018T161400.894002Z/report.json`,
  Windows 11 / Python 3.14.7 / ExifTool 13.59, **20 phases / 52 cases** passed.
  Both native scroll runs retained scrollbar 240, with partial anchors,
  navigation, explicit scrolling and unchanged JPEG hashes passing. Sharing-lock
  recovery and native process cleanup passed; every child exited zero, cleanup
  and temporary-workspace removal were verified, and harness hashes match.
  This closes the required Windows functional verification. No subjective
  visual acceptance or full Windows pytest run is claimed.
- Maintainer authorized the scroll-fix commit on 2026-10-18. Unrelated pending
  folder-refresh changes are preserved and excluded from this commit.

## Commit isolation — 2026-10-18

The scroll fix is committed independently of pending scoped-folder-refresh work.
An exported staged snapshot passed Ruff, full Linux offscreen pytest **399 passed,
four Windows skips, 33 subtests passed**, and real-file acceptance **16 phases /
44 passed cases**. The inspected snapshot report is
`tests/acceptance/reports/20261018T181043.954686Z/report.json`; all child exits,
cleanup, workspace removal and harness hashes were verified against staged files.
The combined Windows report above also includes the uncommitted folder-refresh
phase; its scroll cases use the same scroll scenario as this commit.

One additional isolated suite run segfaulted in the existing duplicate-copy
background-preview navigation test. That test passed in isolation and the entire
suite then passed without a parallel acceptance run. The crash is not claimed
fixed by this change. No push requested.
