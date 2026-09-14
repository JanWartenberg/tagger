# Autocomplete Match Navigation

Status: ready-for-agent
Priority: medium

## Goal

Make tag autocomplete easier to use when multiple suggestions match the typed
text. The completion popup should clearly identify one active suggestion and
support keyboard selection and cycling.

## Desired Interaction

- One suggestion is highlighted whenever multiple matches are displayed.
- `Enter` accepts the highlighted suggestion.
- `Tab` cycles through matching suggestions.
- Up/down arrow keys move the highlighted suggestion.
- `Enter` accepts the suggestion selected with the arrow keys.

## Constraints

- Preserve the existing autocomplete vocabulary and matching behavior.
- Keep normal text-entry, command-line, and tag-input Enter/Tab behavior when
  no completion popup is active.
- Keep completion navigation keyboard-driven and compatible with the existing
  focused tag input workflow.
