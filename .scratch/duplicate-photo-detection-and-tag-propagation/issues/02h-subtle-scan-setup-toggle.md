# 02h — Subtle Scan setup toggle with discoverable shortcut

Status: completed
Category: bug
Priority: medium
Milestone: M9 — Repeatable real-file acceptance

## Goal

Avoid the bright green checked-state fill on the Scan setup collapse button.
Keep the toggle inside the Scan setup frame, with Alt+U in its tooltip only.

## Delivery and acceptance

- Neutral palette-based button fill in both expanded and collapsed states;
  maintainer accepted the color.
- Text and arrow communicate state; hover and focus remain visible.
- Label is simply Scan setup, within the section frame when expanded.
  When collapsed, the same toggle moves immediately left of Add folder in the
  view header, centered vertically at the same height. The empty frame is hidden.
  Alt+U is shown only in the tooltip.
  Shortcut behavior is unchanged. Accessible name describes Show/Hide.
- Regression checks neutral rendered fill, label/arrow presentation, and Alt+U.
- Maintainer accepted collapsed placement and Alt+U on 2026-10-03. Expanded
  placement, preserved selection and Alt+S/new-scan reopening were subsequently
  accepted on the same date.
- Qt tests verify position, equal button heights, shortcut, focus recovery and
  reclaimed review space.

## Comments

Follow-up after maintainer accepted fixes 02e/02f/02g. Integration-suite final
visual acceptance remains open; this ticket replaces those resolved UI blockers.

## Session handoff — 2026-10-03

Maintainer visual acceptance received: collapsed Scan setup placement, Alt+U and
reduced text density are accepted. Changes are included in the requested checkpoint commit. Recorded checks:
340 passed, four Windows skips, 33 subtests passed; Ruff passes. Windows regression report `20261003T213738.131220Z` passed and was verified. Edit mode removal
is undecided. Maintainer subsequently confirmed expanded placement, selection preservation
and Alt+S/new-scan reopening on 2026-10-03.
