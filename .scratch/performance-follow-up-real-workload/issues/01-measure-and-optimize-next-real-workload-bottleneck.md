# 01 — Measure and Optimize the Next Real-Workload Bottleneck

Status: ready-for-agent
Category: performance
Priority: medium
Blocked by: Scheduling deferral — complete one to three other topics first

## Next Action

After the deferral, run the real ExifTool/photo-copy benchmark and compare its
costs with the existing synthetic Windows results. Rank the remaining measured
bottlenecks, define one bounded optimization and success criterion, then
implement only that optimization.

## Candidate Areas

- ExifTool subprocess startup and JSON parsing.
- Metadata batch size and retry behavior.
- `_sync_paths` path statistics, database lookup, and deletion reconciliation.
- Workspace snapshot/filter recalculation.
- Qt files-pane rendering and event-to-render latency.

These are candidates only; measurements must choose the scope.

## Acceptance Criteria

- [ ] The benchmark records revision, Windows/Python/ExifTool versions, dataset,
      cold/warm state, repeat count, and end-to-end timings.
- [ ] Metadata writes are measured only on disposable photo copies.
- [ ] CPU, I/O, subprocess, SQLite, memory, and UI responsiveness costs are
      recorded where applicable.
- [ ] At least one remaining bottleneck is ranked using measured evidence.
- [ ] One bounded optimization and its success criterion are documented before
      implementation.
- [ ] Repeated before/after runs use the same workload and environment.
- [ ] Existing correctness, refresh recovery, cancellation, and UI tests pass.
- [ ] No optimization is retained if the measured improvement is not meaningful
      or if it adds unjustified complexity.

## Deferred Scope

This ticket does not revisit the already implemented refresh reconciliation
narrowing unless new measurements demonstrate a regression or correctness gap.
