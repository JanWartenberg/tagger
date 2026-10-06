# 01 — Measure and Optimize the Next Real-Workload Bottleneck

Status: completed
Category: performance
Priority: medium
Milestone: M-Future — Unscheduled opportunities
Blocked by: None

## Next Action

Completed: focused Windows paired evidence and final local regression checks
pass. Production read blocks are 1,000; refresh stays at 200. No further benchmark
required. Maintainer authorized review, fixes and commit; final review evidence
is recorded below. Earlier checkpoints record investigation history.

## Candidate Areas

- ExifTool subprocess startup and JSON parsing.
- Metadata batch size and retry behavior.
- `_sync_paths` path statistics, database lookup, and deletion reconciliation.
- Workspace snapshot/filter recalculation.
- Qt files-pane rendering and event-to-render latency.

These are candidates only; measurements must choose the scope.

## Acceptance Criteria

- [x] The benchmark records revision, Windows/Python/ExifTool versions, dataset,
      cold/warm state, repeat count, and end-to-end timings.
- [x] Metadata writes are measured only on disposable photo copies.
- [x] CPU, I/O, subprocess, SQLite, memory, and UI responsiveness costs are
      recorded where applicable.
- [x] At least one remaining bottleneck is ranked using measured evidence.
- [x] One bounded optimization and its success criterion are documented before
      implementation.
- [x] Repeated before/after runs use the same workload and environment.
- [x] Existing correctness, refresh recovery, cancellation, and UI tests pass.
- [x] No optimization is retained if the measured improvement is not meaningful
      or if it adds unjustified complexity.

## Deferred Scope

This ticket does not revisit the already implemented refresh reconciliation
narrowing unless new measurements demonstrate a regression or correctness gap.

## Measurement checkpoint — 2026-10-06

Baseline on Linux/WSL, Python 3.11.2, ExifTool 12.57, revision `f0b35c2` plus
the new harness: three repeats, 1,000 generated 1024×768 JPEG copies, Unicode
paths and IPTC/XMP tags, fresh indexes and warm OS caches. No true cold-cache
or camera-original claim. Artifact: `perf/results/real-before.json`.

| Scenario | Median |
| --- | ---: |
| Read 1,000 photos | 1.595 s |
| Initial index | 1.673 s |
| Unchanged index synchronization | 0.026 s |
| Full refresh | 1.718 s |
| Save one / ten photos | 0.162 / 1.634 s |
| Discovery / workspace | 0.005 / 0.001 s |

Ranked hypotheses: (1) avoidable extra process starts in large metadata reads;
(2) ExifTool's necessary per-file work; (3) Python/SQLite normalization and
upserts. File discovery/workspace overhead is negligible at this scale.
The earlier synthetic Windows 30,000-file timings isolate different costs;
they are context, not a comparable baseline or Windows validation.

### Bounded experiment and success criterion (before implementation)

Increase only the adapter's `read_keywords_many` block from 200 to 1,000
paths. UTF-8 argument-file transport already removes command-line length limits.
Keep the refresh service's 200-photo subgroup, retry boundary and time budget,
and all writes/error handling unchanged. Do not add a persistent ExifTool process.

Retain only if three-repeat same-environment median bulk-read and initial-sync
times both improve by at least 10%, with 1,000-photo subprocess count reduced
from five to one, correctness unchanged and no excessive transient Python
memory (target: less than 3 MiB extra peak at this fixture size). Diagnose
memory separately with cProfile/tracemalloc; do not compare profiled timing to
timing-only results. Native Windows timing and camera-original workloads remain
required before claiming benefits there.

### Portable result (experiment; default reverted after Windows evidence)

The experiment changed only `_KEYWORD_READ_BATCH_SIZE` to 1,000. Refresh still submits groups
of 200; no subprocess persistence, write batching, index reconciliation or UI
logic changed. Nine subprocess-boundary pytest cases cover zero/single/boundary/
multiple blocks, Unicode record identity, keyword/date preservation and later
JSON/process failures. Four cases failed on the old process-count behavior
before the change, then passed. A real 1,001-photo run also passed: two read/sync
processes, six refresh processes, all photos indexed.

Confirmed using the same final harness with `--read-batch-size 200` and `1000`,
three repeats each, identical seed hash and parameters:

| Scenario | 200 paths | 1,000 paths | Improvement |
| --- | ---: | ---: | ---: |
| Bulk read | 1.653 s | 1.428 s | 13.6% |
| Initial index | 1.692 s | 1.494 s | 11.7% |
| Full refresh (unchanged subgroups) | 1.728 s | 1.744 s | No improvement claimed |

Artifacts: `perf/results/real-paired-200.json`, `real-paired-1000.json`.
Both read and initial-index calls fell from five to one in every repeat;
refresh retained five. The first independent before/after comparison also
passed the 10% criterion (10.7% read, 11.2% initial index).

Separate profiling: read peak Python allocation rose from 1,154,680 to
1,688,495 bytes (about 0.51 MiB extra); initial-index peak rose from 2,526,144
to 2,919,709 bytes. Child-process memory and UI rendering were not measured.
Baseline bulk read spent 1.565 of 1.595 seconds waiting for ExifTool; Python
CPU was 0.034 seconds versus child CPU 1.562 seconds. SQLite initial-index
statement counts were 8,009. OS block counters and all per-repeat timings are
in the JSON reports. This supports reducing process starts, not speculative
Python/SQLite work or changed write semantics. Generated JPEGs are 24,941 bytes
each; larger camera-file and disk-I/O performance is not established.

Passed: Ruff check/changed-file format, 364 offscreen pytest cases, four
Windows skips, 33 subtests. Independently inspected portable real-file report:
`tests/acceptance/reports/20261006T160518.906332Z/report.json`, ten phases and
28 cases across both backup settings, with verified child cleanup. These are
regression checks; large-read acceptance comes from the new harness and tests.
At this checkpoint, unrun: native Windows benchmark, native lock/cleanup rerun, camera-original and
cold-cache timings, UI event-to-render timings. No checks waived. Existing
Windows lock/cleanup acceptance remains unchanged because writes and process
lifecycle did not change.

### Requested Windows evidence

Run sequentially in the activated development environment; only disposable,
generated photos are written:

```text
python perf/profile_real.py --photos 1000 --repeats 3 --read-batch-size 200 --json-out perf/results/real-windows-200.json
```

```text
python perf/profile_real.py --photos 1000 --repeats 3 --read-batch-size 1000 --json-out perf/results/real-windows-1000.json
```

Both reports are now supplied and independently inspected; findings follow.

### Windows evidence and rollback — 2026-10-06

Environment: Windows 11 build 26300, Python 3.14.7 AMD64, ExifTool 13.59,
revision `f0b35c2` plus working changes. Both timing-only reports use three
repeats, 1,000 generated 1024×768 JPEGs, 24,929 bytes each, identical seed hash
`41da9f5c50fe2327a8c503771751c10b131740505547f893cdee28758f4af07d`.
This is inspected evidence, not just maintainer-reported summary timings.

| Scenario | 200 paths | 1,000 paths | Elapsed change |
| --- | ---: | ---: | ---: |
| Bulk read | 3.548 s | 3.031 s | −14.6% |
| Initial index | 3.253 s | 4.368 s | +34.3% |
| Unchanged sync (no ExifTool) | 0.094 s | 0.788 s | +742.2% |
| Refresh (same 200-path subgroups) | 3.416 s | 6.167 s | +80.6% |
| Discovery (no ExifTool) | 0.043 s | 0.236 s | +449.2% |

Initial-index median ExifTool wall time fell from 2.939 to 2.180 seconds,
with five versus one processes; SQLite counts remained 8,009. Refresh kept
five processes and 11,109 statements, but its non-subprocess time rose sharply.
The 200-path run's third repeat already slowed unrelated operations, and the
1,000-path run remained slow outside ExifTool. First bulk reads were outliers
(14.384 and 21.942 seconds). OS caches warm from generation do not guarantee
a warmed first ExifTool read or a stable system workload.

These controls show timing drift across unrelated work; they do not identify
its cause. Background load, filesystem/security activity and normalization cost
remain hypotheses, not established findings. No causal initial-index regression
from block size is asserted, but the predeclared overall retention criterion
was not met on Windows. The production default is therefore restored to 200;
the private constant remains solely to permit same-revision benchmark overrides.
Tests now cover both the unchanged default and the experimental 1,000-path
override, including later-block failures. No production speedup is retained.
Rollback verification passed: Ruff check/format and full offscreen pytest,
373 passed, four Windows skips, 33 subtests. Previously inspected real-file
regression evidence covers the same small requests under either block size;
write behavior remains unchanged.

Next required evidence: run the 1,000-path variant first, then 200 paths, five
repeats each under otherwise comparable, quiet conditions. Inspect all repeats
and unchanged-operation controls, not just medians. Use separate JSON filenames
to preserve the initial reports. Do not close the ticket or claim Windows
optimization acceptance until the contradiction is resolved.

### Reverse-order Windows reports and tighter feedback loop

Independently inspected `perf/results/real-windows-repeat-1000.json` and
`real-windows-repeat-200.json`: five repeats, 1,000 first, same environment,
revision, fixture hash and dimensions as the first Windows comparison.

| Scenario | 200 paths | 1,000 paths | Elapsed change |
| --- | ---: | ---: | ---: |
| Bulk read | 3.949 s | 3.227 s | −18.3% |
| Initial index | 5.236 s | 3.652 s | −30.3% |
| Unchanged sync (no ExifTool) | 0.773 s | 0.089 s | Controls remain mismatched |
| Refresh (same 200-path subgroups) | 6.446 s | 5.871 s | No block-size benefit inferred |

The reverse-order read/sync medians meet the numeric threshold, but the unchanged
controls vary strongly within and between runs. For example, candidate unchanged
sync spans 0.084–0.801 s; its initial sync spans 2.480–4.542 s. First bulk reads
remain outliers (24.908 s at 1,000, 13.452 s at 200). Favorable medians do not
resolve the original comparison's opposite initial-index result. ExifTool wall
time still favors larger blocks, but the reliable total benefit remains open.

To reduce maintainer repetition and confounding, added `--compare-batches`:
one generated fixture, a full untimed metadata warmup with duration recorded,
alternating variant order, fresh index per variant, only read/sync/unchanged-sync
measurements. Each sample records block size and pair position; JSON preserves
per-pair gains and raw timings. No measurements are discarded as outliers.
The production default remains 200. Run the following single Windows command:

```text
python perf/profile_real.py --photos 1000 --repeats 6 --compare-batches --json-out perf/results/real-windows-paired.json
```

This replaces further separate broad-workload repeats. Inspect neighboring
paired changes against the unchanged-sync controls before applying the original
10% read/initial-sync retention threshold. If controls remain unstable, report
that limit rather than accepting the favorable aggregate alone.

Local paired validation: `perf/results/real-linux-paired.json`, four pairs at
1,000 photos, median within-pair improvement 12.7% read / 13.4% initial sync.
All samples indexed 1,000 photos; processes were five versus one. Unchanged-sync
medians remained near 0.025 s. Real 201-photo/two-pair CLI smoke and its pytest
passed, including both orderings, 200-path boundary crossing and fresh indexes.
Ruff and changed-file formatting passed.

The first new full pytest run had 373 passes and one failure in the unchanged
preview characterization test: elapsed time 0.425 s exceeded 0.4 s. A targeted
rerun then saw the prior photo's pending preview start as well as the latest
photo. No preview implementation or test was changed in this ticket. This
verification instability is recorded separately from the benchmark findings.
The unchanged full rerun passed: 374 tests, four Windows skips, 33 subtests
(116.33 s). The cause of the earlier preview-test failures remains undiagnosed;
they were not fixed or waived. No commit; the remaining blocker is focused
native Windows paired timing evidence.

### Final Windows paired evidence — 2026-10-06

Independently inspected `perf/results/real-windows-paired.json`, supplied by
the maintainer: same Windows 11/Python 3.14.7/ExifTool 13.59 environment and
seed hash, six pairs on one fixture, three pairs per ordering, warmup recorded
as 15.857 s. All 36 measured samples have the expected read/index counts and
all initial indexes contain 1,000 photos. Read/sync subprocess count is five
at 200 paths and one at 1,000 in every pair.

| Scenario | 200-path median | 1,000-path median | Median within-pair gain |
| --- | ---: | ---: | ---: |
| Bulk read | 4.122 s | 3.665 s | 10.7% |
| Initial index | 5.795 s | 5.138 s | 11.2% |
| Unchanged sync (control) | 1.002 s | 0.964 s | 3.3% |

The original at-least-10% median read/initial-sync criterion is met on Windows
as well as Linux. Five of six pairs improve end-to-end reading; five of six
improve initial indexing. The ExifTool component improves in every pair
(median gains 20.3% read and 21.2% sync); control matching in the last two pairs
supports the gain in both orderings. The first pair is unfavorable and retained
in all calculations. Unchanged-sync controls still vary about 0.09–1.05 s, so
these are noisy fixture measurements, not a guaranteed 11% improvement for
every run or real photo library.

Decision: retain the single bounded change, `_KEYWORD_READ_BATCH_SIZE = 1000`.
No more Windows performance repetitions required for this ticket. Refresh
subgroups, writes, retries, process lifecycle, reconciliation and UI remain
unchanged. Prior Linux memory evidence stays within the 3 MiB allowance.
Windows execution was maintainer-run; the JSON was agent-inspected. Native
lock/cleanup reruns, camera-original/cold-cache and UI rendering timings remain
unrun, not waived. No broader performance claims are made.

Final verification passed: Ruff check/changed-file format; offscreen pytest
374 passed, four Windows skips, 33 subtests in 89.94 s; real-file runner report
`tests/acceptance/reports/20261006T164501.259170Z/report.json` independently
inspected, ten phases, 28 cases and verified process cleanup. Includes both
backup settings and existing refusal/persistence regressions. No new test
failures in this final run. Earlier preview-test instability remains documented,
not claimed fixed. Ticket completed; implementation/docs/tests remain uncommitted.

## Pre-commit review

Maintainer authorized review, fixes and commit on 2026-10-06. Reviewed staged
and unstaged diffs plus the three new source/test files; no staged changes were
present initially. No blocking finding in the application read-block change.

- Medium, benchmark validity: assertions disappear under Python `-O`. Added
  an early refusal before creating fixtures/results; regression test passes.
- Medium, write verification: `all()` over an empty result could pass and only
  IPTC tag presence was checked. Reused the strict read verifier for post-write
  checks: complete record count, both exact keyword sets, readable fields and
  preserved capture date. Added missing/mirror/date/unreadable regressions.
- Low, index reset: deletion failures were swallowed. Propagate the failure
  before timing a purported fresh index; added a locked-index regression.
- Low, handoff drift: removed obsolete rollback/waiting-state bullets from the
  current backlog handoff. Investigation history stays in this ticket/review.

The application change remains only the larger read block; no new Windows
timing run is needed for these benchmark validation fixes. Relevant real-file
regression evidence remains valid because production code did not change.
Final review validation: Ruff check/format, 380 offscreen pytest cases, four
Windows skips, 33 subtests (41.62 s), and Git diff checks passed. All actionable
findings fixed; no remaining commit blocker or question. Implementation,
benchmark, tests and review/acceptance notes are committed together under the
maintainer's authorization. No push.
