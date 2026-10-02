# 01 — Build and review the real-file integration suite

Status: ready-for-agent
Category: testing
Priority: high
Milestone: M9 — Repeatable real-file acceptance
Blocked by: --

## Goal

Deliver the bounded subproject in [the specification](../spec.md) so the maintainer
can repeat metadata acceptance without manual fixture setup, copy/paste or cleanup.

## Next action

Deliver external-change/missing-file refusal, Windows sharing-lock partial
failure/retry and robust Windows process-tree cleanup. The normal-path matrix
passed on Windows. Harness relocated to `tests/acceptance/`; run
`.\.venv\Scripts\python tests\acceptance\run.py` from the repo root on Windows.
See that folder's PLAN.md, README.md and REVIEW.md for evidence and limitations.

## Acceptance

- [x] Generated temporary JPEG fixtures and isolated settings/index/workspace.
- [x] Real ExifTool exercised through production workflow at confirmed seams.
- [x] Cancel/confirm, subset, canonical IPTC/XMP, backups and persistence coverage.
- [ ] External-change/missing-file rejection and Windows partial-failure/retry.
- [ ] Explicit runner fails on missing required dependencies; useful evidence report.
- [ ] Guaranteed cleanup, bounded waits and no original-photo access.
- [ ] Documented one-command Windows run and minimal visual smoke checklist.
- [ ] Review recorded, findings addressed and existing suite/lint still passing.

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
- Old sibling folder contains only undeletable virtual-environment remnants;
  Windows must remove that folder. Do not reuse the old virtual environment.
- Safety/retry, abrupt-exit cleanup, final review and visual acceptance remain open.
