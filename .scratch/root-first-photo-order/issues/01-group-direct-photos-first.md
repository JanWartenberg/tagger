# 01 — Group Direct Photos First

Status: in progress
Category: feature
Priority: medium
Blocked by: None

Implementation and local verification are finished. The ticket remains open
only for the necessary native Windows verification below. The maintainer accepted
the visible result and authorized committing after one final review/fix round;
no Windows automated results were supplied by that acceptance.

## Scope

Implement the [spec](../spec.md), preserving scrolling, filtering, selection and
multiple-folder drop order. Keep sorting in background discovery, not in the Qt
widget. Replace refreshed blocks in the workspace and restore scroll anchors
after batched refresh rendering.

## Verification

- TDD: coordinator grouping failed before the discovery change; refresh ordering
  failed before block reconciliation and refresh sort changes.
- TDD: the large filtered F5 case moved a partial anchor from -7 to 424 pixels
  before batched-scroll restoration; it passes after the fix.
- Focused suite: 49 tests passed on Linux offscreen.
- Ruff, all eight modified Python files' formatting and whitespace checks passed.
- Full Linux offscreen suite: 514 passed, four Windows skips, 33 subtests.
- Two independent read-only reviews per round, three rounds total: no code findings.
  Round 1 independently reran 31 coordinator/workspace and 22 workspace/UI tests.
  The final round flagged stale commit-authorization wording, which is corrected.
  Before committing, 49 focused tests, Ruff and affected-file formatting passed
  again; final reviewers independently passed 49 focused and 22 workspace/UI tests.
- Final real-file report passed and independently inspected:
  `tests/acceptance/reports/20261115T191453.847767Z/report.json`, 20 phases / 56
  cases, backups off/on, ExifTool 12.57. All phase exits, process-tree cleanup,
  workspace removal and harness hashes verified. Report SHA-256:
  `b0b72484b077589019396732529b0e4afcb87533adc521d8aa7d954322a76cf3`.
- The acceptance README's expected case counts were corrected to match the
  runner's current required cases: 56 on Linux and 60 on Windows.
- Windows native scroll, sharing-lock and process-cleanup checks: unrun here.
- No checks waived. No new appearance check; prior visual acceptance stands.

## Necessary Windows Verification

Run the focused new Qt regressions and real-file matrix from the development
environment. Supply the resulting report for inspection; Linux cannot establish
native delayed scrolling, sharing-lock or Windows process-cleanup behavior.

```powershell
$env:QT_QPA_PLATFORM = "offscreen"; .\.venv\Scripts\python -m pytest -q tests/test_folder_refresh_ui.py
```

```powershell
.\.venv\Scripts\python tests\acceptance\run.py
```
