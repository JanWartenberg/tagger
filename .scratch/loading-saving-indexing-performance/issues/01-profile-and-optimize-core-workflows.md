# 01 — Profile and Optimize Core Workflows

Status: ready-for-agent
Priority: medium
Category: performance
Milestone: M6 — Maintainability and performance
Blocked by: None

## Next Action

Establish a reproducible baseline for loading, saving, and indexing before
substantial refactoring. Record available benchmark environments and dataset
sizes, including any missing access to a representative Windows photo library.

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

## Comments

Created at the user's request as one of exactly two tickets in M6. Coordinate
baseline capture with the refactoring ticket; optimization does not depend on
completion of all refactoring work.
