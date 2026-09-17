# 01 — Simplify and Deduplicate Code

Status: completed
Priority: medium
Category: maintenance
Milestone: M6 — Maintainability and performance
Blocked by: None

## Next Action

Completed. Both selected M6 cleanups are implemented and validated; no further
implementation is planned for this ticket.

## Selected Cleanup Scope

1. **Completed — remove duplicated IPTC-empty membership state.**
   `PhotoWorkspace` now provides the membership used by MainWindow's current-view
   and refresh comparisons. The Qt adapter retains only its presentation and
   request state. A focused characterization test covers the public membership
   interface while a filename condition narrows visible results.
2. **Implemented — remove the duplicated action-handler registries.** Every
   `ActionSpec` records a `handler_name`; `MainWindow` now resolves and validates
   that named callable at the existing dispatch seam. The separate no-argument
   and argument-handler dictionaries are removed, so adding an action has one
   source of handler truth. Focused characterization tests cover both invocation
   shapes and preserve exact unknown-action and missing-handler errors.

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

The second cleanup removes 51 repeated handler mappings and their two registry
builders without adding another module or changing the action catalogue. The
full 258-test Linux offscreen suite passes, along with Ruff lint, Ruff formatting,
and `git diff --check`. An existing preview-debounce timing test failed
intermittently during stress validation but passed in the final full run; the
action dispatch path does not participate in that workflow. The user reports
that pytest and the Windows acceptance check pass for the second cleanup.

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
