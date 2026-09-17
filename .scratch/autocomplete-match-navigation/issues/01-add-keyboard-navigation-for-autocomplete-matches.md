# 01 — Add Keyboard Navigation for Autocomplete Matches

Status: ready-for-agent
Category: feature
Priority: medium
Milestone: M7 — Startup correctness and autocomplete navigation
Blocked by: None

## Problem

Tag autocomplete can show multiple matches, but the interaction does not make
one match clearly active or provide consistent keyboard controls for choosing
among the matches.

## Goal

Provide a clear highlighted autocomplete match and allow users to accept or
cycle through suggestions without leaving the tag input.

## Acceptance Criteria

- [ ] When multiple matches are shown, exactly one match is visibly highlighted.
- [ ] `Enter` accepts the currently highlighted match.
- [ ] `Tab` cycles through the matches and updates the highlighted match,
      wrapping at the end.
- [ ] Up and down arrow keys move the highlighted match through the suggestions.
- [ ] `Enter` accepts the match selected with the arrow keys.
- [ ] The selected completion replaces or inserts text according to the current
      autocomplete behavior without corrupting the tag input.
- [ ] Single-match, no-match, and empty-input behavior remains correct.
- [ ] `Enter`, `Tab`, and arrow keys retain their existing behavior when no
      autocomplete popup is active.
- [ ] Add deterministic tests for highlighting, Tab cycling, arrow navigation,
      and accepting a match with Enter.

## Constraints

- Preserve the existing autocomplete vocabulary, matching, and focus behavior.
- Do not change command-line completion behavior unless it shares the same
  component and the change is explicitly covered.
- Keep the interaction usable with the existing keyboard-driven tag workflow.

## Validation

- Run focused autocomplete and tag-input tests.
- Run the full test suite and Ruff for modified files.
