# 01 — Add Resumable Background Full-Index Refresh

Status: needs-triage
Category: feature
Priority: low
Milestone: M2 — Reliable, scalable index operations
Blocked by: None

## Goal

Make long full index refreshes durable and resumable without sacrificing responsive tagging and search workflows.

## Proposed Scope

- Batch full-refresh metadata reads and commit durable progress after each batch.
- Resume interrupted work after restart.
- Expose non-modal progress and resumed state.
- Keep search available against committed index data and prevent tag mutations from waiting behind the entire refresh.

## Required Triage Before Implementation

- Checkpoint model and invalidation rules.
- Queue priorities, batch size, cancellation, and mutation interaction.
- Progress, restart, failure, and search-consistency UX.

## Comments

Created from the product backlog after a 30,000-photo full refresh demonstrated the need for durable incremental progress.
