# Performance Follow-up: Real Workload and Next Bottleneck

Status: completed
Priority: medium

## Scheduling

The maintainer lifted the scheduling deferral on 2026-10-06 and authorized
starting measurements. It is
intentionally separate from the current refresh-reconciliation optimization so
that its measurements and scope can be revisited with fresh evidence.

## Checkpoint — 2026-10-06

Portable measurements are implemented and verified: reproducible real-ExifTool
harness and one larger-read-block experiment. Three-repeat paired Linux/WSL medians
improved bulk reading by 13.6% and initial indexing by 11.7%, with about 0.51 MiB
extra peak Python allocations for bulk reading. Ruff, 364 offscreen tests and
28 portable real-file cases passed. The ticket records measurements and limits.
Native Windows paired reports are supplied and independently inspected: bulk
read improved 14.6%, but initial indexing worsened 34.3% while unrelated controls
also slowed sharply. The acceptance criterion is unmet; production defaults
are restored to 200-path blocks. The ticket remains needs-info for a reverse-order
Windows repeat to distinguish timing drift from block-size effects. No commit.
Reverse-order reports were also inspected: medians favor larger blocks, but
unrelated controls still drift. A focused `--compare-batches` mode now alternates
variants on one warmed fixture; native Windows paired results remain required.
After rollback, Ruff and the full offscreen suite passed: 373 tests,
four Windows skips and 33 subtests.

## Final paired evidence

The maintainer supplied the focused Windows report; the agent independently
inspected all six pairs. Median within-pair gains meet the original thresholds:
10.7% read, 11.2% initial index. ExifTool time improves in every pair; aggregate
timings remain noisy and do not establish camera-original or cold-cache gains.
Retain 1,000-photo adapter read blocks; refresh subgroups remain 200. Final
Ruff/format checks, 374 offscreen tests (four Windows skips, 33 subtests) and
28 portable real-file cases passed. Ticket completed; no further Windows
performance run required and no commit performed. Earlier checkpoints above
are historical; their waiting/rollback states are superseded by this result.
The maintainer subsequently authorized review, finding fixes and commit.
Pre-commit fixes strengthen only benchmark validation; the accepted application
read-block behavior remains unchanged.
Review validation passed: Ruff/format and 380 offscreen tests, four Windows
skips, 33 subtests. All actionable findings fixed; the authorized commit includes
implementation, benchmark, tests and acceptance notes. No push.

## Goal

Continue TAGGER performance work using real ExifTool/photo-copy measurements and
select the next evidence-backed optimization instead of optimizing based only
on synthetic profiles.

## Scope

- Measure representative loading, metadata saving, indexing, refresh, and
  workspace workflows with the real ExifTool adapter where available.
- Include Unicode paths/tags and cold/warm runs.
- Reassess remaining candidates such as ExifTool process overhead, metadata
  batch sizing, `_sync_paths` filesystem/SQLite work, and workspace/UI rendering.
- Select and implement at most one bounded optimization in this ticket.

## Constraints

- Use photo copies for all metadata writes.
- Preserve metadata correctness, backup behavior, error semantics, resumable
  refresh behavior, and UI responsiveness.
- Keep filesystem, metadata, and SQLite work off the Qt UI thread.
- Do not introduce speculative complexity when measurements do not justify it.
