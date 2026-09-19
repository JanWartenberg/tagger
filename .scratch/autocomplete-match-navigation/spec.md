# Autocomplete Match Navigation

Status: completed
Priority: medium
Milestone: M7 — Startup correctness and autocomplete navigation

## Goal

Make tag autocomplete easier to use when multiple suggestions match the typed
text. The completion popup should clearly identify one active suggestion and
support keyboard selection and cycling.

## Desired Interaction

- Use compact horizontal chips (prototype option C), not a dropdown or context list.
- Empty input and typing alone show no suggestions. Tab starts completion.
- Multiple matches open with exactly one highlighted chip; the input stays editable.
- Left/right arrows select the previous/next chip, wrapping at either end.
  This supersedes the original up/down requirement following prototype feedback.
- Tab extends a longer shared prefix when available; otherwise it cycles forward.
- Typing while completion is open filters candidates; empty/no-match input closes it.
- Enter accepts the highlighted suggestion into the input and closes completion,
  without submitting a mutation. A second Enter uses the existing add-tag workflow.
- Clicking a chip selects it without stealing input focus or submitting a tag.
- Use one horizontally scrollable row, never wrap chips or widen the window.
  Keep the active chip visible, show its position/total and overflow indicators.
- Handle 100 matches with the same controls; typing narrows the list.
- Preserve immediate Tab completion for a single match, normal cursor keys when
  closed, and existing Escape/focus-loss dismissal and explicit Add/Ctrl+Enter behavior.

## Implementation and validation

Implemented in `tag_completion.py` and integrated with the existing tag input.
The PyQt prototype established the chip layout, horizontal navigation, shared-prefix
completion, and two-stage Enter behavior. Production keeps the existing single-match
Tab shortcut and Escape focus behavior. Command-line completion is unchanged. The
first acceptance pass found no issues.
Deterministic main-window tests cover 100-match scrolling, wraparound, filtering,
selection, and the mutation boundary; the full offscreen suite passes.

## Constraints

- Preserve the existing autocomplete vocabulary and matching behavior.
- Keep normal text-entry, command-line, and tag-input Enter/Tab behavior when
  no completion popup is active.
- Keep completion navigation keyboard-driven and compatible with the existing
  focused tag input workflow.
