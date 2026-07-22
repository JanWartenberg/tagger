# Photo Workspace View-State Consistency

Status: completed
Priority: medium

## Problem Statement

A failed IPTC-empty filter started from a database-search view can restore the prior visible paths while reporting the IPTC-empty view mode as active. The model then exposes a contradictory logical state to the Qt adapter and user controls.

## Solution

Define one coherent state transition for starting, succeeding, clearing, and failing an IPTC-empty filter from every Photo Workspace view. Each snapshot must describe the visible paths and active view consistently.

## User Stories

1. As a TAGGER user, I want filter controls to describe the photos currently shown.
2. As a TAGGER user, I want a filter failure to leave me in an understandable view.
3. As a TAGGER user, I want clearing a filter or search to have predictable restoration behavior.
4. As a maintainer, I want a snapshot to have no contradictory mode and visibility combination.

## Implementation Decisions

- Keep Photo Workspace as the single owner of logical view mode, visible paths, selection repair, filter-operation identity, and restoration state. Qt owns only physical scroll positioning.
- Starting an IPTC-empty filter captures the complete current logical view as its restoration state: normal or database-search mode, visible paths, selected paths, and active path. While the scan is pending, leave that prior view visible and leave the checkbox unchecked.
- Do not render progressive filter batches. Apply only a completed successful result atomically.
- On success, switch to IPTC-empty mode, check the checkbox, and select the first matching photo. A successful empty result keeps the checkbox checked and has no selection.
- On failure, discard every partial result, uncheck the checkbox, and restore the captured logical view. Restore its selected/active photo and have the Qt adapter scroll that photo to the top of the files pane. Report the failure normally in non-modal feedback.
- Rechecking the checkbox after failure always starts a fresh scan. Do not retry automatically and do not add a separate retry action.
- Clearing a successfully applied IPTC-empty filter restores its captured logical view, including database-search results when that was the source, selected/active photo, and Qt scroll-to-selected-top behavior.
- Render Qt controls from the resulting snapshot; controls must not infer a second logical mode.
- Preserve stale-result rejection: completions from an obsolete filter operation cannot alter a newer view.

## Testing Decisions

- Extend pure Photo Workspace transition tests to cover normal → filter → success/failure/clear and search → filter → success/failure/clear.
- Assert that pending and partial batches leave the source view unchanged; final success applies atomically; and failure restores the captured mode, visible paths, selection, and active path.
- Cover successful empty results, explicit fresh restart after failure, and stale-result rejection.
- Add offscreen adapter coverage that verifies checkbox state, no progressive pane replacement, and scroll-to-restored-selection behavior on failure and clear.

## Out of Scope

- The deferred complete reverse-search mode or frozen-snapshot filter semantics.

## Further Notes

Implemented by ticket 01: the Photo Workspace retains its logical source view during scans, applies completed filter results atomically, and restores source state after failure or clearing.