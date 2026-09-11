# Maintainability Refactoring

Status: ready-for-agent
Priority: medium

## Goal

Simplify existing code, remove genuine duplication, and improve maintainability
without changing TAGGER's user-visible behavior or metadata semantics.

## Scope

Inspect current code and tests, identify concrete cleanup opportunities, and
implement a bounded set of high-value changes in small reviewable steps. Prefer
clearer responsibilities, simpler control flow, and fewer competing sources of
truth over new abstraction layers or a wholesale rewrite.

## Constraints

- Preserve keyboard workflows, Photo Workspace behavior, canonical IPTC rules,
  error reporting, Unicode path handling, and index compatibility.
- Keep blocking work off the UI thread.
- Capture the M6 performance baseline before substantial refactoring.
- Add characterization coverage where changed behavior lacks a reliable test.
- No new product features, AI integration, or speculative architecture migration.

## Completion

Record the selected cleanup scope and rationale before changing code. Complete
that scope, run relevant regression tests and Ruff checks, and summarize removed
duplication and simplified responsibilities. Recheck affected performance
scenarios against the shared baseline; record remaining opportunities without
silently expanding M6 into additional tickets.
