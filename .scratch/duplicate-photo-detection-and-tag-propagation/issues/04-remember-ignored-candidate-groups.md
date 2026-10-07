# 04 — Remember Ignored Duplicate Candidates

Status: ready-for-agent
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
commit. Status stays ready-for-agent pending inspection of the Windows automated
report; that run and detailed scaling checks remain unconfirmed, not waived.
Previous unrelated M9 acceptance remains valid.

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
- Remaining: inspect the Windows automated report before closing the ticket.
  Detailed scaling checks remain unconfirmed. Preserve the accepted quick check;
  previous Windows native lock/cleanup acceptance is not claimed revalidated here.
- Maintainer explicitly authorized commit; implementation and acceptance notes
  are committed together. No push requested.
