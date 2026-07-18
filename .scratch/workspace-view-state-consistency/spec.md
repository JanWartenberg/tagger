# Photo Workspace View-State Consistency

Status: needs-triage
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

- Keep Photo Workspace as the single owner of logical view mode, visibility, selection repair, and restoration state.
- Explicitly define filter failure behavior when the previous view is normal and when it is database search.
- Render Qt controls from the resulting snapshot; controls must not infer a second logical mode.
- Preserve stale-result rejection and current selection/scroll responsibilities.

## Testing Decisions

- Extend pure Photo Workspace transition tests to cover search → filter → failure, search → filter → success, and clear operations.
- Assert snapshot mode, visible paths, selection, and active path together.
- Add one offscreen adapter test for the selected failure behavior.

## Out of Scope

- The deferred complete reverse-search mode or frozen-snapshot filter semantics.

## Further Notes

Grilling is required before tickets because the desired user-visible restoration behavior after a filter failure has not been chosen.