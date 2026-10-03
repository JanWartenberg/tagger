# 02f — Reserve space for the candidate queue scrollbar

Status: completed
Category: bug
Priority: medium
Milestone: M9 — Repeatable real-file acceptance

## Goal

Keep candidate cards fully visible when horizontal overflow introduces a scrollbar (reported with seven candidates).

## Acceptance

- Queue height includes card content, layout margins, frame and scrollbar.
- Cards remain vertically visible with horizontal overflow and larger fonts.
- Maintainer confirms Windows appearance at the usual window size.

## Comments

Reported during M9 visual acceptance. Blocks integration-suite acceptance.

Fix: replace the fixed maximum queue height with a content-derived fixed height
including frame and scrollbar space. Update on body layout/resize changes,
including font changes. Regression uses eight groups, horizontal overflow and
a larger font, checking every card's vertical bounds. Maintainer confirmed: "02f is fixed". Accepted.
