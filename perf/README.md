# TAGGER core profiling harness

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
