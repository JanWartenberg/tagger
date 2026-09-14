# 01 — Profile and Optimize Core Workflows

Status: ready-for-agent
Priority: low
Category: performance
Milestone: M6 — Maintainability and performance
Blocked by: None

## Next Action

Deferred. Later, complete the remaining concurrent deletion and
recovery/cancellation validation, review the diff, and decide whether to close
this ticket or move remaining real-ExifTool/photo-copy validation to the
follow-up. Do not change UI logic.

## Current Checkpoint

- Profiling harness and combined reports are available under `perf/`.
- Synthetic Windows 30,000-file timings cover discovery, sync, refresh, and
  workspace behavior; real ExifTool/photo-library validation is still open.
- The normalized internal upsert change is retained; its path-identity test and
  indexing regression suite pass.
- The refresh queue batching experiment was reverted after no meaningful
  end-to-end improvement.
- The refresh reconciliation now reuses a durable discovered-path manifest and
  rescans only directories whose mtime changed during the run; unchanged roots
  no longer receive a second full recursive traversal.

### Session 5 — Windows sync after normalized upsert change

User-run 30,000-file timing-only sync result, with the same fixture parameters as
the baseline:

| Measurement | Before | After |
| --- | ---: | ---: |
| Sync duration | 9.069 s | 8.113 s |
| `indexing.normalize_path` calls | 90,000 | 30,000 |
| SQLite statements | 150,067 | 150,067 |
| Synthetic ExifTool files | 30,000 | 30,000 |

This is an approximately 10.5% end-to-end improvement on this Windows
synthetic run. The comparison is useful because the workload and environment
match; repeat count is still one. The unchanged SQLite and ExifTool counters
show that this change isolated path normalization rather than changing index
work.

## Investigation Plan

This ticket is deliberately executed in stages. The first stage is reconnaissance,
not optimization: establish a reproducible workload, inspect likely expensive code
paths, measure them, and only then select a bounded change.

### Core scenarios

1. Open a photo folder and load the Photo Workspace.
2. Build a fresh index.
3. Refresh an existing index after no file changes.
4. Refresh an existing index after representative file changes.
5. Run indexed tag/date search and the main workspace filters.
6. Save tags on one photo and on a representative multi-photo selection.

### Measurement dimensions

Each applicable scenario records end-to-end latency, repeat count, revision,
OS, Python/ExifTool versions, dataset characteristics, and cold/warm state.
The profiling pass additionally records Python hotspots, CPU and memory usage,
UI-thread blocking, file opens, ExifTool invocations, and SQLite query activity.

### Dataset tiers

- small committed/synthetic fixture for fast regression checks,
- larger synthetic fixture for scaling behavior,
- real photo copies where available, including Unicode paths and tags,
- representative Windows library measurements when available.

Synthetic data is suitable for repeatability and scaling comparisons; it does
not replace real ExifTool/Windows validation. Missing environments are recorded
as gaps, never filled with invented measurements.

### Decision rules

Classify findings as unavoidable I/O, avoidable repeated work, algorithmic cost,
UI-thread work, or infrastructure cost. Do not optimize filesystem traversal or
individual metadata reads merely because they consume time; prioritize measurable
avoidable work and define a success criterion before changing code.

### Static inventory (Session 1)

These are testable suspects, not yet measured bottlenecks:

1. `FileSystemPhotoDiscovery.discover`, `PhotoIndex.sync_root`, and the
   reconciliation phase of `PhotoIndex.refresh_step` each perform recursive
   traversal. The refresh path may traverse the root more than once.
2. `PhotoIndex._sync_paths` stats every discovered supported path before deciding
   which files need ExifTool; this is likely necessary for freshness, but its
   cost should be separated from metadata reads.
3. `PhotoIndex._sync_paths` loads all indexed paths for deletion reconciliation;
   measure its memory and latency on large indexes.
4. `PhotoIndex._take_refresh_path_batch` persists directory and path queues with
   per-entry SQLite operations; compare queue overhead with filesystem traversal.
5. `PhotoIndex._index_refresh_paths` reads ExifTool data in subgroups and retries
   failed groups; measure subgroup count, retry impact, and commit cost.
6. `ExifTool._run` starts one subprocess per operation, while
   `read_keywords_many` and `scan_iptc_empty` chunk at 200 paths; measure process
   startup and JSON parsing separately from ExifTool file work.
7. `PhotoIndex.load_iptc_empty_photos` performs a filesystem `is_file()` check
   for every database candidate after the SQLite query; verify whether this
   protects a real stale-result case at an acceptable cost.
8. `PhotoWorkspace.snapshot` recomputes filtered membership and constructs visible
   and selected tuples. Frequent UI calls may repeat O(n) work for large workspaces.
9. `MainWindow._render_photo_workspace` rebuilds a `QListWidget` completely;
   the batched renderer reduces blocking but may still make large renders costly.
10. Indexed search and filter transitions can trigger multiple snapshots and view
    renders; measure event-to-render latency before considering coalescing work.

The first profiling harness should cover suspects 1, 2, 5, 6, 8, and 9. The
remaining suspects can be promoted only if the measurements show material cost.
Filesystem traversal and individual metadata reads remain baseline costs unless
profiling demonstrates avoidable repetition around them.

### Session ledger

- Session 0 — scope and measurement contract: completed above.
- Session 1 — static codebase inventory: completed above.
- Session 2 — automated profiling harness: completed in `perf/profile_core.py`;
  usage and interpretation are documented in `perf/README.md`.
- Session 3 — baseline measurements: next action.
- Session 4 — bottleneck ranking and bounded optimization scope.
- Session 5+ — one optimization and one before/after validation cycle at a time.

## Interim Results

### Session 3 — Windows synthetic 30,000-file run

Source: user-run profiling artifacts in `perf/results/core-30000-*.prof`.
Environment visible in the profile: Windows, Python 3.14; the exact revision,
repeat count, and cold/warm state still need recording. The fixture contains
30,000 disposable JPG/JPEG files in a nested local directory tree and uses the
synthetic ExifTool adapter.

Observed under `cProfile+tracemalloc`:

| Scenario | Profiled time | Main observations |
| --- | ---: | --- |
| Discovery | 1.55 s | `is_file` and `scandir` dominate; treat as baseline filesystem cost. |
| Sync | 18.58 s | 11.39 s in `normalize_path`; 6.06 s in Windows `getfinalpathname`; 1.65 s in SQLite `execute`; 2.13 s in `stat`. |
| Refresh | 30.04 s | 16.74 s in `normalize_path`; 8.24 s in `getfinalpathname`; 7.17 s in refresh batch handling; 3.03 s in SQLite `execute`. |
| Workspace | 0.73 s | 0.70 s in repeated filtered visibility; 90,000 basename calculations. |

These are not user-visible timings because profiling instrumentation adds
overhead and ExifTool is synthetic. The call counts are nevertheless strong
evidence that path resolution is repeated work. The first optimization candidate
is to normalize paths at explicit boundaries and preserve an internal
normalized-path invariant. This must be validated for Unicode, relative,
absolute, Windows, and symlink-sensitive path behavior before implementation.

Discovery itself is not a first optimization target: its dominant operations
are the required filesystem traversal and file classification. Refresh queue
SQLite work and repeated workspace basename/filter work remain secondary
candidates.

### Measurement correction

`perf/profile_core.py` now supports `--no-profile` for timing-only runs. The
refresh setup index is outside the profiled refresh operation. The next baseline
must use timing-only runs for comparison and profiled runs only for hotspot
inspection.

### Session 3 — timing-only Windows synthetic run

User-run command: `python .\\perf\\profile_core.py --scenario all --photos 30000
--depth 30 --no-profile --json-out perf\\results\\core-30000-timing.json`.
This is one run; repeat count and cold/warm state are still open.

| Scenario | Timing-only duration | Counters |
| --- | ---: | --- |
| Discovery | 0.834 s | 30,000 discovered |
| Sync | 9.069 s | 30,000 files in one synthetic ExifTool call; 150,067 SQLite statements |
| Refresh | 14.316 s | 150 synthetic ExifTool calls; 212,526 SQLite statements |
| Workspace | 0.123 s | 30,000 workspace paths; 1,000 visible after filename filter |

The unprofiled timings confirm that sync and refresh dominate this synthetic
workload. They do not represent real metadata I/O: the synthetic ExifTool
returns immediately, and the fixture uses a local disposable filesystem.

### Normalization trace experiment

The harness now supports `--trace-normalization`, which counts calls by owning
module without changing the returned path. A 100-file timing-only run reported
200 `indexing.normalize_path` calls during sync and 355 during refresh; the
synthetic ExifTool contributes no `exif_tool.normalize_path` calls because it is
not the real adapter. This confirms that the current profile's normalization
cost is in TAGGER's indexing path, while a real-ExifTool run is still needed to
measure adapter-side normalization.

Next, compare the trace on a real-adapter/photo-copy workload if available, then
write characterization coverage for path identity before attempting to reduce
normalization at internal boundaries.

### First bounded change — normalized internal upsert path

`PhotoIndex` now keeps `upsert_state` as the public normalizing boundary and uses
`_upsert_state_normalized` from sync/refresh paths that already normalized their
input. This removes one redundant `Path.resolve()` per indexed photo without
changing public path handling or metadata behavior.

The path-identity characterization is now covered by
`PhotoIndexCanonicalKeywordFactTests.test_sync_normalizes_unicode_and_redundant_absolute_path_segments`.
The indexing test module passes (19 tests); Ruff passes with a writable cache
outside the repository because the local `.ruff_cache` is not writable.

The after-sync run with tracing measured 8.113 s and 30,000 indexing
normalizations, compared with the 9.069 s untraced baseline and 90,000
normalizations. Because tracing modes differ, the duration improvement is
provisional. The after-refresh run with tracing measured 18.098 s versus the
14.316 s untraced baseline; this is likewise not a regression finding until an
untraced comparison is available.

The subsequent untraced Windows runs measured 8.298 s and 8.865 s for sync, and
18.608 s and 16.423 s for refresh. Sync remains below the 9.069 s baseline, with
identical SQLite and synthetic ExifTool counters; its mean of two after-runs is
8.582 s (about 5.4% lower). Refresh remains above the 14.316 s baseline, but the
spread between after-runs is 2.185 s. This is currently anomalous and is not
attributed to the change; phase-level timings are needed before changing refresh
logic. Likely external sources include filesystem/Dropbox/antivirus variance.

The harness now includes `refresh_steps` timing entries in refresh JSON results,
covering each discovery, reconciliation, and completion step. It also reports
`refresh_internal_timings` for durable queue batches, metadata batches, and final
reconciliation.

### Session 5 — Refresh phase timing

User-run 30,000-file timing-only result after the normalized-upsert change:
16.558 s total, 150 synthetic ExifTool calls, and 212,526 SQLite statements.
The 30 discovery steps each take approximately 0.35–0.45 s, contributing
roughly 12 s. The transition labelled `reconciling` takes only 0.004 s; the
final step takes 4.576 s and contains the full-root `rglob` plus final
`_sync_paths` reconciliation. The harness should treat that final step as
reconciliation, not as a successful no-op completion.

This separates the refresh cost into two concrete areas: durable queue/batch
processing during discovery, and the intentional second full traversal plus
reconciliation. Both are now better targets than generic ExifTool or UI work.
The durable queue remains functionally required for resumability; any change
must preserve checkpoints and cancellation behavior.

The next harness revision measures these internal totals directly, without
changing application behavior. A small smoke run passed; the indexing test
module and Ruff also remain green.

The 30,000-file Windows refresh run with internal timings measured 12.242 s.
The 30 discovery steps contributed approximately 9 s in total. Internal totals
were 3.270 s for durable queue batches, 3.988 s for metadata batches, and
2.612 s for final reconciliation. The phase totals overlap some surrounding
connection/step overhead and therefore do not sum exactly to the end-to-end
value.

This run is faster than the 14.316 s baseline, but prior after-runs ranged from
16.423 s to 18.608 s. The broad run-to-run spread means no percentage
improvement is claimed for refresh yet. The breakdown does identify durable
queue writes, metadata/upsert work, and final reconciliation as separate
optimization candidates. The next bounded candidate is batching queue SQLite
writes while preserving checkpoint and cancellation semantics.

### Session 7 — Narrowed refresh reconciliation

The refresh checkpoint now retains discovered photo paths and the mtime of each
visited directory. Final reconciliation stats the retained paths, rescanning
only directories whose mtime changed during the refresh. This preserves
concurrent additions and removals while avoiding a second full-root traversal on
unchanged trees. The manifest and directory state are cleared on completion,
cancellation, and checkpoint restart; old checkpoints without the manifest fall
back to the original full traversal.

A regression test covers a photo added after its root directory was discovered.
The indexing tests pass (20 tests), the full suite passes (246 tests), and Ruff
passes for the changed files. A local Linux timing-only 30,000-file run measured
3.637 s end to end, with 0.908 s for final reconciliation; this is not a
Windows baseline and is not compared quantitatively with the existing Windows
runs.

The user then ran five timing-only 30,000-file Windows 11 measurements at
revision `4b09bc7de18ec5acc8f71c062c865fc34597cc05`, with Windows 11 25H2
(OS build `10.0.26200.9445`), Python 3.14.7, ExifTool 13.59, and the 30-level
synthetic fixture.
The end-to-end refresh times were 12.828 s, 12.150 s, 12.800 s, 12.050 s, and
12.109 s: mean 12.387 s, standard deviation 0.391 s, minimum 12.050 s, and
maximum 12.828 s. Final reconciliation averaged 3.135 s. Internal means were
3.462 s for durable queue batches, 4.112 s for metadata batches, and 2.566 s
for reconciliation. All runs processed 30,000 files in 150 synthetic ExifTool
calls and 243,073 SQLite statements.

Against the earlier 14.316 s single-run baseline, the current mean is about
13.5% lower. This is encouraging but not a matched repeated before/after
comparison; real-ExifTool/photo-copy validation remains open.

### Session 8 — Windows synthetic timing-only run

The user supplied a timing-only run at revision
`4b09bc7de18ec5acc8f71c062c865fc34597cc05` using Windows 11 25H2 (OS build
`10.0.26200.9445`), Python 3.14.7, and ExifTool 13.59. These environment
versions are fixed for this ticket. Command:

`python perf\\profile_core.py --scenario all --photos 30000 --depth 30 --no-profile --json-out perf\\results\\core-30000-real-timing.json`

Results:

| Scenario | Elapsed | Counters |
| --- | ---: | --- |
| Discovery | 0.719 s | 30,000 discovered |
| Sync | 5.846 s | 30,000 indexed; 1 ExifTool call; 150,067 SQLite statements |
| Refresh | 10.424 s | 30,000 indexed; 150 ExifTool calls; 243,073 SQLite statements |
| Workspace | 0.109 s | 30,000 workspace paths; 1,000 visible after filename filtering |

Refresh internal timings were 3.113 s for durable queue batches, 3.298 s for
metadata batches, and 2.371 s for reconciliation. The supplied JSON does not
record repeat count or cold/warm state. Despite the installed ExifTool version
being recorded, this harness run uses the synthetic ExifTool adapter; real
ExifTool/photo-copy validation remains open in the follow-up ticket.

Windows validation also reports 20 passing indexing tests and 246 passing full-suite
tests in 13.94 s. Ruff reports nine pre-existing findings in unchanged code and
tests (three `BLE001`/`S110` findings in `indexing.py` and six `SIM117` findings
in `tests/test_indexing.py`); the current reconciliation additions introduce no
reported Ruff findings.

### Session 6 — Batched refresh queue writes: rejected

A temporary change collected discovered directories and photo paths and inserted
each category with `executemany`. Checkpoint progression, resume, completion,
cancellation, and failure tests remained green. The Windows 30,000-file timing
run measured 12.227 s, effectively identical to the preceding 12.242 s run;
queue timing was 3.166 s versus 3.270 s. The statement count was unchanged.

The change was reverted because the total improvement was within normal run
variance and did not justify retaining extra complexity. The queue remains
unchanged. This is a documented negative result, not an open implementation.

## Acceptance Criteria

- Cover the scenarios and environment details in the [parent spec](../spec.md).
- Supply repeatable profiling/benchmark commands and recorded baseline results.
- Rank observed bottlenecks and select a bounded optimization scope with a
  measurable success criterion before implementation.
- Implement evidence-backed optimizations, or document why none is justified.
- Compare repeated before/after measurements on the same workload; preserve
  correctness and check UI responsiveness as well as throughput.
- Test writes only on photo copies; run relevant regression tests and Ruff.
- Clearly distinguish locally measured results from pending Windows validation.
- Windows synthetic validation is now recorded; real-ExifTool/photo-copy
  validation remains pending and is deferred to the separate
  [performance follow-up](../../performance-follow-up-real-workload/issues/01-measure-and-optimize-next-real-workload-bottleneck.md).

## Comments

Created at the user's request as one of exactly two tickets in M6. Coordinate
baseline capture with the refactoring ticket; optimization does not depend on
completion of all refactoring work.
