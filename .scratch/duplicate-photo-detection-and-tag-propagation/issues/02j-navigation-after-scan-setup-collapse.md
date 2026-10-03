# 02j — Keep navigation available after collapsing Scan setup

Status: completed
Category: bug
Priority: medium
Milestone: M9 — Repeatable real-file acceptance

## Goal

Alt+U must preserve usable review focus. h/l navigates groups and j/k navigates
photos without entering Edit mode; text inputs retain normal typing.

## Delivery

- Navigation routes now apply in either mode; s/t/i retain Edit mode semantics.
- Scan setup toggle handles review key events. Focus restoration uses the original
  focus before the toggle changes parents, then restores it after relocation.
- Regression drives Alt+U and all four navigation keys, and verifies normal typing.

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
