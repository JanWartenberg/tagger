# 02l — Show copy results in the footer

Status: needs-info
Category: feature
Priority: medium
Milestone: M9 — Repeatable real-file acceptance
Blocked by: maintainer Windows regression and footer visual confirmation

## Goal

Remove the interposed results widget from Duplicate review. Use the existing
footer for subtle save feedback and access to results, failures/retry and ignored
candidates, without consuming review space.

## Delivery

- Deleted the in-page status container, layout and scroll area entirely.
- One native footer menu button shows Saved N or aggregate pending/failed/cancelled
  attention. It is visible only in Duplicate review when results exist.
- Menu entries retain per-group outcomes and counts, explicit failed-only retry
  and ignored-candidate restoration. New scans clear the footer and menu.
- Tests verify footer ancestry, removed review widget, view switching, no height
  growth with many results, coexisting footer controls and retry/restoration.
- Real-file harness observes public footer menu actions and triggers the same Qt
  action to reopen outcomes; metadata/hash/backup assertions are unchanged.

## Comments

Maintainer rejected the first compact in-page design on 2026-10-03: its empty
scroll area and cramped Completed line added no value. Requested complete removal
and footer use. Windows report `20261003T221813.709522Z` passed before this revision;
it validates 02j/02k but does not validate the footer change.

## Next

Maintainer verifies that the strip above the candidate cards is gone, save/failure
feedback lives in the footer, and the menu opens outcomes/retry/restoration.
Rerun the Windows real-file regression against this revision.

## Validation — footer revision

Ruff/format and diff checks pass. Focused Qt tests: 44 passed, two subtests.
Full offscreen pytest: 344 passed, four Windows skips, 33 subtests passed.
Portable report `20261003T222741.128862Z`: ten phases/28 cases, both backup modes,
process cleanup and workspace removal passed. Native Windows checks are not run
on Linux. Footer rendering inspected offscreen; new Windows regression and
maintainer footer confirmation remain open.

## Checkpoint handoff — 2026-10-03

Footer revision is included in the requested checkpoint on
`prototype/duplicate-review-ui`. Next: Windows matrix and footer visual check.
Preserve result actions for outcomes, failed-only retry and ignored restoration;
the rejected in-page widget must stay deleted. Do not reopen accepted 02j/02k.
