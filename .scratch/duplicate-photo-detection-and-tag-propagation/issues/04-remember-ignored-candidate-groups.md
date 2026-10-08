# 04 — Remember Ignored Duplicate Candidates

Status: completed
Category: feature
Priority: low
Milestone: M-Future — Unscheduled opportunities
Blocked by: 02

## Goal

Allow users to ignore a duplicate-candidate group without being shown the same
candidate again in a later scan.

## Scope

- Record an explicit Ignore decision for a candidate group.
- Define stable identity and lifecycle for ignored candidates.
- Exclude remembered candidates from later review without hiding new evidence.
- Provide a way to inspect, restore, or clear ignored candidates.

## Acceptance Criteria

- [x] Ignoring a candidate removes it from the active review list.
- [x] A later scan does not automatically re-present the same ignored candidate.
- [x] New or changed candidate evidence is not silently suppressed.
- [x] Users can inspect and undo ignored-candidate decisions.
- [x] Tests cover persistence, identity changes, restore, and clear behavior.

## Out of Scope

- Automatically confirming duplicates.
- Deleting, moving, or consolidating files.
- Tag propagation.

## Agreed rules — 2026-10-07

- Persist per index across restarts in `.tagger/ignored_candidates.sqlite`,
  independent of the rebuildable photo cache.
- Identity: detector plus sorted normalized member paths and each member's
  timestamp/source field. Exclude tags, readability and scan-local group IDs.
- Changed identity is reviewed again; old saved decisions remain inspectable
  until explicitly restored or cleared. Matching original evidence stays ignored.
- Ignore advances only after a successful save; failure keeps the candidate
  eligible and records a visible Session error. All storage and image loading
  happen off the UI thread.
- Header / `:ignoredcandidates` and ignored footer entries open the read-only
  list. Inspect photo previews, paths, saved capture evidence and historical tags.
  Missing photos display Preview unavailable. Inspection does not restore.
- Restore removes one decision and updates any matching current queue; Clear
  all ignores requires confirmation and affects only the selected index.

## Delivery state

Implemented and verified on Linux; two review rounds completed with no remaining
findings. Maintainer reported a successful quick acceptance check and authorized
commit. The supplied Windows report was independently inspected: all sixteen
phases/42 cases and native cleanup passed on committed revision `1d6d909`.
Ticket completed with maintainer quick acceptance; detailed scaling checks remain
unreported, not claimed passed or waived. Previous unrelated M9 acceptance remains valid.

## Verification — 2026-10-07

- Passed: Ruff check, changed-file format checks, diff whitespace check.
- Passed: final full offscreen pytest, 391 tests; four Windows-only skips.
- Passed: 11 focused persistence/Qt tests, including filesystem-free identity,
  restart, index isolation, changed membership/evidence, tag-only retention,
  explicit restore/clear, failed save and closing a list during loading.
- Passed and independently inspected: real-file report
  `tests/acceptance/reports/20261007T175150.109036Z/report.json`, fourteen process
  phases and 38 cases across both backup settings; cleanup and workspace removal
  verified. New cases prove restart persistence, read-only photo inspection,
  restore, clear and changed provenance without application photo writes.
- First extended acceptance attempt failed on an assertion before Qt finished
  showing controls; bounded visibility waits fixed the harness. The next run
  passed, as did the final run after the review fix.
- Two independent read-only reviewers per round. Round 1 found repeated
  filesystem resolution during UI identity hashing; fixed by pure lexical
  normalization of already canonical scan paths, with a failing-then-passing
  regression. Round 2: no findings; both independently ran 11 focused tests.
- Maintainer-reported: quick feature acceptance passed; no platform details or
  automated report were supplied. This is not independently inspected evidence
  of a full Windows suite pass or detailed scaling checks.
- Follow-up: the supplied Windows report was independently inspected below.
  Detailed scaling checks remain unreported; preserve the accepted quick check.
- Maintainer explicitly authorized commit; implementation and acceptance notes
  are committed together. No push requested.

## Windows verification — 2026-10-07

Maintainer supplied `tests/acceptance/reports/20261007T200507.473386Z/report.json`;
the agent independently inspected the synced report, case matrix and native
cleanup log. Windows 11, Python 3.14.7, ExifTool 13.59; clean commit `1d6d909`.
All recorded harness hashes matched the scripts in committed revision `1d6d909`.

- Passed: sixteen process phases/42 cases across both backup settings, including
  persistent ignores, fresh-process read-only inspection, restore, clear and
  changed capture evidence.
- Passed: native sharing-lock partial failure/failed-only retry for both backup
  settings; native process cleanup probes (five tests).
- Verified: every phase returned zero with process-tree cleanup; both disposable
  workspaces were removed.
- Manual acceptance: maintainer's prior quick check is accepted. The automated
  report explicitly does not validate appearance; detailed scaling observations
  remain unreported, not claimed passed or waived. No repeat quick check requested.

Ticket completed. This documentation update is not a new commit authorization.

## Maintainer follow-up

Maintainer explicitly confirmed ignoring and resetting work. That manual
acceptance is preserved while the separately scoped ticket 05 removes Edit mode.
