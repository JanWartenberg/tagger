# TAGGER core profiling harness

## Real ExifTool workload

`profile_real.py` complements the synthetic harness below. It generates a
1024×768 JPEG seed and 1,000 disposable copies in Unicode directories, with
Unicode IPTC/XMP keywords and an EXIF capture date. It uses production discovery,
ExifTool argument-file transport, indexing, resumable refresh, PhotoWorkspace,
and tag-mutation service. It accepts no personal-photo input path. Requires
the development environment and ExifTool on PATH.

```sh
python perf/profile_real.py --photos 1000 --repeats 3 --json-out perf/results/real.json
```

Windows uses the same command from an activated development environment.
For a same-revision comparison, run once with `--read-batch-size 200` and once
with `--read-batch-size 1000`, writing separate JSON files. This changes only the
benchmark process's read block; production files and refresh subgroups are not
modified.
The production read default is 1,000, accepted after paired Linux and Windows
measurements; refresh still uses 200-photo subgroups. `--read-batch-size 200`
reproduces the previous adapter block. If unchanged scenarios
drift between runs, compare again in reverse order with more repetitions rather
than attributing the difference to block size. A slow first read may occur even
after fixture generation; OS-cache warmth alone does not remove other startup
or filesystem effects.

For noisy results, use the focused paired comparison instead of separate broad
runs. It creates one fixture, records a full untimed metadata warmup, then
alternates 200/1,000 and 1,000/200 order. Each variant receives a fresh SQLite
index; only bulk read, initial sync and unchanged-sync controls are timed. No
tag mutations occur in this mode. An even repetition count balances order.

```sh
python perf/profile_real.py --photos 1000 --repeats 6 --compare-batches --json-out perf/results/real-windows-paired.json
```

JSON includes every variant's block size/order, per-pair percentage differences
and their medians, alongside absolute timing medians and subprocess counts.
Compare neighboring pairs and unchanged-sync controls; an overall median alone
does not remove system drift. This mode cannot combine with `--read-batch-size`
or profiling.
Results include revision/worktree, platform, Python/ExifTool versions, seed hash
and size, repeat count, median and individual end-to-end timings, subprocess
time/calls/output bytes and SQLite statement counts. On POSIX, CPU and filesystem
block I/O are reported separately for Python and child processes; these counters
are unavailable on Windows. Every repeat rebuilds a fresh SQLite index; OS caches
are warm after generating files. This is **not** a cold-cache measurement or a
camera-original dataset. UI event-to-render latency is not measured here.

Metadata writes use only temporary copies; writes are reread and reset outside
timings. Verification checks all selected files, both keyword fields and the
capture date. Run without Python optimization (`-O`/`PYTHONOPTIMIZE`); the
harness rejects disabled assertions. Index-reset failures stop the run instead
of allowing a cached index to masquerade as fresh. Each ExifTool invocation is
bounded to 30 seconds. Whole-workload
diagnostics with Python allocation peaks and cProfile are a separate run:

```sh
python perf/profile_real.py --photos 1000 --repeats 1 --profile-out perf/results/real.prof --json-out perf/results/real-profile.json
```

Do not compare profiled timings to timing-only results. Compare identical
fixture parameters and environment before/after; Linux results do not establish
Windows performance. Keep useful measurement summaries in the ticket since raw
`perf/results/` artifacts are ignored.

This harness lives outside the application runtime and uses only disposable
temporary data. It imports TAGGER's core modules to exercise real discovery,
index, and workspace logic, but uses a deterministic `SyntheticExifTool`; no
photo metadata is written and no real photo library is touched.

## Run

From the repository root:

```bat
python perf\profile_core.py --scenario all --photos 1000 --depth 10 ^
  --profile-out perf\results\core.prof ^
  --json-out perf\results\core.json
```

On Linux/macOS, use `/` instead of `\` and `\` line continuations as usual.
The default fixture is 1,000 disposable JPG/JPEG files. Increase `--photos` for
scaling runs, for example `30000`.

Individual scenarios:

```text
--scenario discovery   filesystem discovery only
--scenario sync        discovery result plus initial index synchronization
--scenario refresh     initial index followed by a full refresh
--scenario workspace   PhotoWorkspace membership/filter/snapshot work
```

`--profile-out` is a filename prefix when `all` is selected. The command above
therefore writes `core-discovery.prof`, `core-sync.prof`,
`core-refresh.prof`, and `core-workspace.prof`. It also writes one combined
`core-report.txt` containing the top 30 cumulative-time and internal-time
functions for every scenario. Use `--report-out` to choose another report path.
No interactive `pstats` commands are needed. Inspect a `.prof` file manually
only when a deeper drill-down is useful:

```text
python -m pstats perf/results/core-discovery.prof
```

At the `pstats` prompt, enter `sort cumulative` and then `stats 30`.
The JSON output contains elapsed time, measurement mode, synthetic ExifTool
call/file counts, SQLite statement counts, result counts, and peak `tracemalloc`
memory. Refresh results additionally include per-step phase timings and
internal totals for queue batches, metadata batches, and final reconciliation.
For trustworthy timing comparisons, use `--no-profile`; this omits
cProfile/tracemalloc overhead and marks the JSON as `timing-only`. Refresh setup
is performed outside the profiled refresh operation, so its profile no longer
includes the initial index build.

Timing-only example:

```text
python perf\\profile_core.py --scenario all --photos 30000 --depth 30 --no-profile --json-out perf\\results\\core-30000-timing.json
```

To measure where repeated path normalization occurs, add
`--trace-normalization`. The JSON then includes `normalize_indexing` and
`normalize_exif_tool` counters for each scenario. This trace is intended for a
focused experiment and adds a small wrapper overhead; use `--no-profile` when
comparing timings.

## Interpretation

This first harness measures TAGGER's Python, SQLite, and coordination overhead
without conflating it with real ExifTool metadata I/O. It therefore cannot
answer how fast a real image library or Windows filesystem is. Those are a
separate validation run using photo copies and the real `ExifTool` adapter.

Always record the revision, OS, Python version, fixture size, repeat count, and
whether the run was cold or warm alongside results. Compare the same command
before and after any change. Do not optimize filesystem traversal or individual
metadata reads solely because they appear in a profile: first establish that
the work is avoidable or repeated.
