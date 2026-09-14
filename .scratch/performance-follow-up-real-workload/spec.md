# Performance Follow-up: Real Workload and Next Bottleneck

Status: ready-for-agent
Priority: medium

## Scheduling

Defer this follow-up until one to three other topics have been completed. It is
intentionally separate from the current refresh-reconciliation optimization so
that its measurements and scope can be revisited with fresh evidence.

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
