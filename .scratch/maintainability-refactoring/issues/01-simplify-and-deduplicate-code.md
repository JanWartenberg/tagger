# 01 — Simplify and Deduplicate Code

Status: ready-for-agent
Priority: medium
Category: maintenance
Milestone: M6 — Maintainability and performance
Blocked by: None

## Next Action

Review the current code and tests, then record a bounded cleanup shortlist with
concrete duplicated logic, unnecessarily complex control flow, or unclear
responsibilities. Start with the clearest behavior-preserving improvements.

## Acceptance Criteria

- Record the selected scope and rationale before implementation.
- Before substantial changes, coordinate the baseline capture in the
  [performance ticket](../../loading-saving-indexing-performance/issues/01-profile-and-optimize-core-workflows.md).
  Full completion of that ticket is not a prerequisite.
- Implement the selected improvements in small reviewable steps without product
  or metadata behavior changes.
- Add regression/characterization tests at affected public seams where needed.
- Run relevant tests and Ruff; compare affected workflows to the baseline.
- Summarize maintainability gains and explicitly record any deferred scope.

## Comments

Created at the user's request as one of exactly two tickets in M6. See the
[parent spec](../spec.md) for behavioral constraints.
