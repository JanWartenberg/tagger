# 02g — Allow Copy shortcut outside Edit mode

Status: completed
Category: bug
Priority: medium
Milestone: M9 — Repeatable real-file acceptance

## Goal

Allow the unambiguous C shortcut in Duplicate review without requiring Edit mode.

## Acceptance

- C opens the existing copy preview in either mode, retaining all guards and explicit confirmation.
- Text inputs retain normal typing; modified shortcuts and other views are unaffected.
- Help and tooltip no longer claim C requires Edit mode.
- Maintainer confirms Windows keyboard behavior.

## Comments

Reported during M9 visual acceptance. Blocks integration-suite acceptance.

Fix: C now has duplicate_review scope instead of duplicate_edit. Existing
view, modifier and text-focus guards remain in force; preview and confirmation
are unchanged. Tooltip/help updated. Regression opens the actual preview outside
Edit mode and verifies cancellation/no writes and normal c typing in text input.
Other modal keys are unchanged. Maintainer confirmed: "02g fixed". Accepted.
Maintainer also questioned the remaining Edit mode; no removal decision yet.
