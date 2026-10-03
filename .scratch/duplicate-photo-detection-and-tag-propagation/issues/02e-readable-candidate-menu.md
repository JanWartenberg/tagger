# 02e — Keep candidate photo context menus readable

Status: completed
Category: bug
Priority: high
Milestone: M9 — Repeatable real-file acceptance

## Goal

Fix gray-on-gray Duplicate review context menus; Photo Workspace menus already have readable light text on dark gray.

## Acceptance

- Candidate image and card menus use the same readable theme as Photo Workspace menus.
- Clicked-photo targeting and selection remain unchanged.
- Automated palette regression passes; maintainer confirms native Windows appearance.

## Comments

Reported during M9 visual acceptance. Blocks integration-suite acceptance.

Fix: own candidate popups at MainWindow instead of the preview label, whose
unscoped placeholder stylesheet leaked gray text into the menu. Shared menu
builder explicitly uses the window palette. Regression exercises image/card
menus under a dark palette; existing clicked-photo action tests remain intact.
Maintainer confirmed: "02e is fixed". Accepted.
