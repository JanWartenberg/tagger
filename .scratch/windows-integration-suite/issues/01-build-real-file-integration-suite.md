# 01 — Build and review the real-file integration suite

Status: needs-info
Category: testing
Priority: high
Milestone: M9 — Repeatable real-file acceptance
Blocked by: maintainer Windows safety/retry run and visual acceptance

## Goal

Deliver the bounded subproject in [the specification](../spec.md) so the maintainer
can repeat metadata acceptance without manual fixture setup, copy/paste or cleanup.

## Next action

Run the newly expanded refusal and sharing-lock/retry matrix on Windows:
`.\.venv\Scripts\python tests\acceptance\run.py` from the repo root.
Normal-path and native cleanup coverage already passed on Windows. This new
slice is implemented, portable refusals pass on Linux, and native sharing-lock
validation is pending. Then perform the minimal `tests/acceptance/VISUAL_SMOKE.md`
checklist; retain explicit findings and do not accept unrun checks.

## Acceptance

- [x] Generated temporary JPEG fixtures and isolated settings/index/workspace.
- [x] Real ExifTool exercised through production workflow at confirmed seams.
- [x] Cancel/confirm, subset, canonical IPTC/XMP, backups and persistence coverage.
- [ ] External-change/missing-file rejection and Windows partial-failure/retry.
- [x] Explicit runner fails on missing required dependencies; useful evidence report.
- [ ] Guaranteed cleanup, bounded waits and no original-photo access.
- [x] Documented one-command Windows run and minimal visual smoke checklist.
- [x] Review recorded, findings addressed and existing suite/lint still passing.

## Comments

Maintainer requested this subproject after accepting M8 rather than continuing
repetitive manual tests. See the latest delivery updates below.

### Session handoff — confirmed boundaries and environment

- The maintainer approved real ExifTool and generated temporary JPEGs. Qt tests
  send events directly to their own offscreen widgets, not desktop-wide mouse or
  keyboard automation; they must not interfere with the user's running app.
- Proceed at the specification's public UI and propagation/mutation seams with
  independent metadata/hash/backup observations. No personal photo fixtures.
- The updated Docker image includes Debian `libimage-exiftool-perl`. The maintainer
  verified `exiftool -ver` in container `pensive_goldberg`: **12.57**.
- Reload the session in that updated container before implementation; recheck
  dependencies there rather than assuming this session's environment changed.
- Linux execution validates portable behavior only. Windows sharing-lock failure
  and retry coverage still requires a Windows run with explicit reporting.
- Branch: `prototype/duplicate-review-ui`. Commit `3e44f88` closed M8 by explicit
  maintainer acceptance and established this subproject; no merge authorized.
- At this initial handoff, no integration-suite code or tests had been implemented.
- Follow-up UI request: ticket
  `../../duplicate-photo-detection-and-tag-propagation/issues/02b-collapse-scan-setup.md`.
- Review each delivery slice, address findings, run Ruff and the existing full
  offscreen suite, then document the single-command integration run.

### Delivery update — first two slices

- At the maintainer's request, the harness lives in the sibling
  `/workspace/tagger-acceptance/` folder, not this Git repository. Existing sample
  JPEGs remain untouched. No production-code changes were needed.
- The original confirmed-copy slice passed locally and in the maintainer's
  Windows report `reports/20261001T202314.789644Z` (ExifTool 13.59).
- The expanded matrix now covers cancel/no-write, selected subsets, canonical
  IPTC versus conflicting source XMP, existing/empty target XMP policy, backups
  off/on with original-byte checks, and fresh-process UI/metadata persistence.
- Linux report `reports/20261001T204212.676644Z` records four passing process phases,
  eight case results and both temporary workspaces removed. The expanded matrix
  was subsequently rerun on Windows; see relocation update below.
- Ruff passed. Full existing suite: first run had the previously observed preview
  scheduling failure; unchanged rerun passed 328 tests and 33 subtests. Both logs
  are preserved; the timing-sensitive test has not been fixed.
- Windows abrupt-exit orphan cleanup, safety/retry cases, final review/acceptance
  and the visual checklist remain open. Do not mark the complete suite accepted.

### Windows confirmation and relocation

- Expanded Windows matrix passed: `tests/acceptance/reports/20261002T152911.296728Z/report.json`.
- Harness and documentation now live in `tests/acceptance/`. All historical reports
  were preserved there; manual JPEGs and index moved to ignored `local-fixtures/`.
- Relocated Linux runner passed: `reports/20261002T153826.873517Z/report.json`.
- Old sibling folder was subsequently removed. Do not reuse the old virtual environment.
- Safety/retry, abrupt-exit cleanup, final review and visual acceptance remain open.

### Process containment slice — Windows validated

- Relocated Windows matrix passed: `reports/20261002T161141.558457Z/report.json`.
- New `tests/acceptance/process_control.py` gates Windows children until assignment
  to a non-inheritable kill-on-close Job Object. Shutdown kills descendants even
  after abrupt child exit and waits for zero active job processes.
- Runner now requires native Windows timeout/descendant, abrupt-exit,
  job-handle-close and assignment-refusal probes before the metadata matrix.
- Rerun the same repo-root Windows command; send the report and cleanup logs on
  failure. Linux cannot validate native Job Object behavior.
- Native cleanup and normal matrix passed: `reports/20261002T162912.910988Z`.

### Refusal and partial-failure/retry slice — awaiting Windows run

- Added real changed/missing source/target refusals at preview and confirmation,
  with unchanged-file positive controls, plus final target-write guard refusals.
- Native sharing-lock scenario uses production UI/worker events: one selected
  target succeeds, one fails under a real Windows sharing handle; explicit retry
  after releasing it must leave successful/unselected files and backups unchanged.
- Both backup settings are covered. Linux requires 28 case results in ten phases;
  Windows additionally requires four sharing-lock results and native cleanup probes.
- Portable slice passed: `reports/20261002T165651.503170Z`.
- No production code needed changes. Native lock/retry and visual acceptance are
  not yet passed. The maintainer must rerun the same Windows command.
- Ruff/format and focused mypy checks pass; full offscreen pytest: 329 passed,
  four Windows-only skips. Two-axis self-review recorded in REVIEW.md.
- Ticket is needs-info pending the maintainer's Windows result and visual smoke;
  no final acceptance or merge into main is implied.

### Windows result and outcome-visibility regression

- Current-commit report `reports/20261002T172205.633827Z` passed cleanup, normal
  paths, refusals and locked-file partial failure with backups off. It failed
  immediately after reopening outcomes: labels existed but Qt had not shown them
  yet. Retry and backup-on phases were not reached; workspace cleanup succeeded.
- Harness now waits for exact visible outcome labels and an enabled visible retry
  button using the existing bounded event-loop wait. Assertions are not weakened.
- A real offscreen Qt-widget regression reproduces the empty-visible-label failure
  before the fix and passes afterward. No mocked photo writes or production changes.
- Portable matrix passed: `reports/20261002T175123.833724Z`; full offscreen pytest:
  330 passed, four Windows skips. Ruff/format and focused mypy pass.
- Next: rerun the same Windows command. Native failed-only retry and backup-on
  lock coverage remain unverified; no final acceptance claim.
