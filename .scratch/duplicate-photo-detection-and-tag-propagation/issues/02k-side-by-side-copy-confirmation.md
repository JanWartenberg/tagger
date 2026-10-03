# 02k — Show source and target side by side in copy confirmation

Status: completed
Category: feature
Priority: medium
Milestone: M9 — Repeatable real-file acceptance

## Goal

Make the confirmation easy to assess: source image/tags on the left, target
image/tags on the right, tags in bold, no redundant confirmation instruction.

## Delivery

- Side-by-side photo columns with bold literal canonical tags. Targets show
  confirmed-empty tags and the proposed copied tags as No tags → copied tags.
- Images load in background workers. Late callbacks cannot update a closed dialog.
- Source stays visible while multiple targets scroll independently. Paths and
  captured backup setting remain visible; y/n/Esc and default Cancel are retained.
- Regression checks layout, bold tags, selected target subset, real image loading,
  large target lists, literal text and cancellation without writes.

## Acceptance — 2026-10-03

Maintainer confirmed the fix/improved confirmation. Windows report
`20261003T221813.709522Z` verified: twelve phases/32 cases, both backup modes,
sharing-lock retry, process cleanup and workspace removal passed. This report
predates the subsequent footer relocation under 02l.

## Validation — 2026-10-03

Ruff passes. Full offscreen pytest: 343 passed, four Windows skips, 33 subtests
passed. Portable real-file report `20261003T220626.449205Z`: ten phases/28 cases
passed; temporary workspaces removed. Windows regression and maintainer acceptance for this ticket are complete.
The subsequent footer relocation is tracked separately under 02l.
