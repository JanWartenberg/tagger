# 01 — Add Keyboard Navigation for Autocomplete Matches

Status: completed
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

- [x] Explicit Tab activation; typing alone does not open suggestions.
- [x] Compact horizontal chips with exactly one highlighted match.
- [x] Enter copies the selected match into the input only; another Enter adds it.
- [x] Tab extends a longer shared prefix or cycles forward, wrapping at the end.
- [x] Left/right arrows navigate horizontally (supersedes up/down per user feedback).
- [x] Typing filters the open matches without corrupting the input.
- [x] Single-match, no-match, and empty-input behavior remains correct.
- [x] Existing Enter, Tab, cursor, Escape, and explicit add behavior outside completion.
- [x] A single scrollable chip row, position/total counter and overflow indicators;
      active match stays visible even with 100 candidates.
- [x] Deterministic tests for highlighting, cycling, arrows, filtering, shared prefix,
      100-match scrolling, mouse selection, and two-stage Enter.

## Constraints

- Preserve the existing autocomplete vocabulary, matching, and focus behavior.
- Do not change command-line completion behavior unless it shares the same
  component and the change is explicitly covered.
- Keep the interaction usable with the existing keyboard-driven tag workflow.

## Validation

- Run focused autocomplete and tag-input tests.
- Run the full test suite and Ruff for modified files.

## Acceptance

First acceptance pass after implementation found no issues.

## Implementation outcome

Implemented compact option C in `tag_completion.py`, integrated into `exif_ui.py`.
No production import of prototype code and no change to command-line completion.
The existing mutation path is invoked only after completion is accepted, not by
completion itself. Single-match Tab completion and Escape's existing focus behavior
are intentionally retained. See the updated parent spec for the approved interaction.

Validation: 265 tests pass in the full Linux/offscreen unittest suite; Ruff check
and formatting pass for modified Python files; `git diff --check` passes.
Review against the prototype, user feedback, and revised acceptance criteria found
and fixed literal ampersand rendering, keypad-Enter handling, and hint repositioning
when the input moves/resizes. No remaining actionable findings in this change.
Native Windows visual validation was accepted without issues in the first acceptance pass.
