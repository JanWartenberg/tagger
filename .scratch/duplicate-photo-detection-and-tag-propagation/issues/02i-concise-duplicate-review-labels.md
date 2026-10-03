# 02i — Reduce repeated Duplicate review guidance

Status: completed
Category: feature
Priority: medium
Milestone: M9 — Repeatable real-file acceptance

## Goal

Reduce persistent prose and repeated explanations without hiding safety restrictions,
selection state, metadata-read failures or copy confirmation.

## Delivery

- Remove redundant confirmation reminder from the view header; preview and its
  explicit confirmation remain unchanged.
- Keep source/target instructions in the action bar, not repeated above cards.
- Move keyboard cheat sheet to Edit mode tooltip and retain current-view help.
- Show group capture time once; retain each photo's EXIF source field and full path.
- Move detector details and general candidate caveat to summary/evidence tooltips.
- Shorter initial empty state, tag labels and non-empty filter label; exact filter
  semantics remain in its tooltip.
- Preserve visible inspection-only restrictions, unknown-tag warnings and status
  rows. Regression verifies concise visible guidance and discoverable details.

## Next

Maintainer accepted reduced text density on 2026-10-03. Concise UI text is now
the default in AGENTS.md. No change to
scan, filtering, copying or Edit mode semantics is intended.

## Session handoff — 2026-10-03

Maintainer visual acceptance received: collapsed Scan setup placement, Alt+U and
reduced text density are accepted. Changes are included in the requested checkpoint commit. Recorded checks:
340 passed, four Windows skips, 33 subtests passed; Ruff passes. Windows regression report `20261003T213738.131220Z` passed and was verified. Edit mode removal
is undecided. Maintainer subsequently confirmed expanded placement, selection preservation
and Alt+S/new-scan reopening on 2026-10-03.
