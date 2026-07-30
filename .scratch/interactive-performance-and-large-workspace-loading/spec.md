# Interactive Performance and Large-Workspace Loading

Status: ready-for-windows-acceptance
Priority: high

## Problem Statement

TAGGER becomes perceptibly slow on a real Windows/Dropbox photo library. Loading approximately 1,200 photos is acceptable, but loading 29,821 photos takes about 20 seconds before the user can work. A `date:2025` search returning 2,910 photos takes about five seconds. During rapid `j`/`k` navigation across roughly 20–30 photos, the final selected photo can take several seconds to show its metadata, suggesting stale background work is occupying the queue.

## Desired Outcome

Keep direct UI acknowledgement responsive while metadata, previews, discovery, and index work continue in the background. The final photo after rapid navigation must not wait behind stale work. Large folder loads must provide useful, truthful progress and be investigated for earlier usable rendering.

## Confirmed Reproduction

`tests/test_main_window_characterization.py` contains a minimal, agent-runnable red test for stale selection work:

```bash
QT_QPA_PLATFORM=offscreen python3 -m unittest \
  tests.test_main_window_characterization.MainWindowCharacterizationTests.test_latest_selection_is_not_delayed_by_stale_metadata_reads -v
```

It uses six rapid selection changes, a constrained one-worker pool, and 100 ms simulated metadata reads. Before a fix it fails because the final selection takes about 0.66 seconds, exceeding the 0.3-second response budget.

## Investigation Order

1. Test and fix stale metadata-read work from rapid selection changes. The current selection token discards stale results but does not prevent their queued Exif reads from running.
2. Measure whether stale preview jobs on the shared global Qt thread pool still delay the final selection after step 1.
3. Measure large-folder discovery separately from workspace/list rendering. Current discovery returns one complete path list, so it cannot display an initial usable batch before traversal completes.
4. Measure `date:` search separately for SQLite time, thread-pool wait time, and rendering time for the returned workspace.
5. Only retain and implement later work that measurements show is material. Do not add a general cache, streaming discovery, or rendering rewrite speculatively.

## Constraints

- The UI must acknowledge selection and pending tag mutations without waiting for ExifTool or SQLite completion.
- Preserve latest-result correctness: stale work must never overwrite the current selection.
- Filesystem traversal, ExifTool, image decoding, and SQLite work remain off the Qt UI thread.
- A progress indicator must not falsely imply that all files are already available or indexed.
- Keep normal indexing and confirmed tag-mutation semantics intact.

## Out of Scope

- Blindly retaining all photo metadata in memory.
- Treating a larger thread-pool size as the only solution.
- Committing to progressive discovery or a virtualized file list before profiling establishes their benefit.
