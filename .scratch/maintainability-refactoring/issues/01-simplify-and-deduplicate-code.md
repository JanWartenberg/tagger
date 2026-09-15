# 01 — Simplify and Deduplicate Code

Status: ready-for-agent
Priority: medium
Category: maintenance
Milestone: M6 — Maintainability and performance
Blocked by: None

## Next Action

Remove the duplicated MainWindow action-handler registries. Resolve and validate
each `ActionSpec.handler_name` at the existing dispatch seam, preserving current
command, shortcut, key-route, and error behavior.

## Selected Cleanup Scope

1. **Completed — remove duplicated IPTC-empty membership state.**
   `PhotoWorkspace` now provides the membership used by MainWindow's current-view
   and refresh comparisons. The Qt adapter retains only its presentation and
   request state. A focused characterization test covers the public membership
   interface while a filename condition narrows visible results.
2. **Remove the duplicated action-handler registries.** Every `ActionSpec`
   records a `handler_name`, while `MainWindow` repeats the same names in separate
   no-argument and argument-handler dictionaries. Resolve and validate the named
   callable at the existing dispatch seam so adding an action has one source of
   handler truth. Preserve unknown-action and missing-handler errors and all
   command, shortcut, and key-route behavior.

Broad MainWindow extraction, index-refresh control-flow changes, storage-format
cleanup, and tiny one-off helper deduplication are deferred: they either overlap
active behavior-sensitive areas or would add shallow modules without enough
leverage for this bounded ticket.

## Interim Checkpoint

The shared M6 performance ticket is completed with synthetic Windows baselines
for discovery, sync, refresh, and workspace operations. One behavior-preserving
indexing cleanup was measured there: avoiding redundant internal path
normalization. The selected work above does not alter indexed data processing or
the measured workspace filtering implementation.

The first cleanup passes Ruff, formatting, `git diff --check`, and the full
248-test offscreen suite on Linux. The same 248-test suite passed on Windows
before the implementation, and a superficial post-change manual acceptance check
found no regression. After fixing three test-harness timing issues exposed by
stress runs—scroll-restoration ordering, worker teardown, and an overly strict
large-render completion timeout—the repeated 112-test Windows MainWindow
characterization loop completed successfully.

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
