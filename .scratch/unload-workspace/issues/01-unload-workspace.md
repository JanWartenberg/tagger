# 01 — Unload the Photo Workspace

Status: completed
Category: feature
Blocked by: None

## Implementation

- Shared command in both views and a compact accessible eject button next to
  each Add folder button.
- Follow-up: match Add folder/eject heights in both views, using their larger
  natural height. Geometry assertions reproduced the mismatch before the fix
  and passed afterward; two independent reviewers found no issues.
  Ruff and the full Linux suite passed again (506 tests, 4 Windows skips,
  33 subtests), as did real-file acceptance in independently inspected report
  `tests/acceptance/reports/20261115T181514.849616Z/report.json` (20 phases /
  60 results, matching harness hashes).
- Reuse workspace/filter/duplicate reset flows; clear the folder refresh target
  and autocomplete cache. Preserve preferences and saved data.
- Invalidate discovery generations, skip queued obsolete discovery, and check
  cancellation between filesystem entries. Existing read/render generations
  reject late search, filter, preview and duplicate results.
- Stop the index status animation and clear departed UI repair/sync tracking.
  Coordinator cancellation preserves missing-result repairs until completion,
  including repeated unload/reload/unload, without retaining stale UI feedback.
- Disable both buttons while tag writes are running/queued and guard the command.

## Validation

- Focused Qt/coordinator tests passed after reproducing missing behavior first.
- Final Linux offscreen suite: 506 passed, 4 Windows skips, 33 subtests passed.
  Ruff check and format check passed. Initial run crashed in the existing Qt
  style test; that module passed separately (9 tests) and subsequent full
  sequential runs passed. The native crash is not claimed fixed.
- Real-file acceptance: 20 phases / 60 results passed, ExifTool 12.57;
  `tests/acceptance/reports/20261115T174146.800597Z/report.json` independently
  inspected. Both backup settings passed; disposable workspaces removed and
  harness hashes match the final files.
- Independent read-only reviews: round 1 found the lingering index status
  animation; round 2 found late repair feedback and canceled sync bookkeeping;
  round 3 found repeated unload could cancel protected repairs. Each confirmed
  defect was reproduced and fixed. Fresh round 4 reviewers both returned no
  findings and independently passed all 13 focused unload tests.
- Maintainer-executed Windows acceptance passed; independently inspected report
  `tests/acceptance/reports/20261115T175936.525074Z/report.json`: Windows 11,
  Python 3.14.7, ExifTool 13.59, 22 phases / 64 results, both backup settings,
  native sharing-lock and process-cleanup checks passed. Disposable workspaces
  removed; recorded harness hashes match current files.
- Maintainer accepted the result after the height adjustment and requested the
  final review and a commit limited to this feature. This records overall
  maintainer acceptance, not a separately reported detailed visual checklist.
  Prior accepted visual checks stay accepted.
- Final pre-commit review found no further code issues. Ruff, affected-file
  format check and all 13 focused unload tests passed again. Existing final full
  suite and Linux/Windows real-file evidence were reused; harness hashes were
  rechecked successfully. Commit authorized for this feature only; no push.
