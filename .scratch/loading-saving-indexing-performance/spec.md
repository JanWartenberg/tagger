# Loading, Saving, and Indexing Performance

Status: ready-for-agent
Priority: medium

## Goal

Profile TAGGER's loading, metadata saving, and indexing workflows, identify actual
bottlenecks, and implement justified optimizations with reproducible evidence.

## Required Scenarios

- Load a photo folder into the Photo Workspace and select a photo to read metadata.
- Save tags on one photo and a representative multi-photo selection; measure
  through confirmed completion, not merely optimistic UI updates.
- Build a fresh index, refresh an existing index, and perform an unchanged scan.
- Include Unicode paths/tags and a representative large library (approximately
  30,000 photos where available). Distinguish cold and warm runs.

## Measurement Contract

Record revision, OS, Python/ExifTool versions, dataset characteristics, commands,
and repeat counts. Capture end-to-end latency, UI responsiveness, and relevant
CPU, I/O, subprocess, SQLite, and memory costs. Use profiles to distinguish
bottlenecks rather than assuming which layer is slow.

Capture the baseline before substantial M6 refactoring. Synthetic fixtures can
support unattended measurements but do not substitute for Windows/ExifTool
validation on representative photos. If that environment is unavailable, record
the gap and request a user-run capture rather than inventing results.

## Constraints and Completion

Preserve metadata correctness, backup behavior, error semantics, resumable index
behavior, and responsive UI interaction. Use photo copies for write benchmarks.
Choose a bounded optimization scope based on measured costs and establish its
success criterion before implementing. Compare repeated before/after runs and
run regression tests. If no worthwhile safe optimization is found, document the
measurements and rationale instead of introducing speculative complexity.
