# Photo Workspace Interface Simplification

Status: ready-for-agent
Priority: medium

## Problem Statement

PhotoWorkspace exposes redundant snapshot fields for view mode and derived active flags, plus a general visibility setter used only by tests. This makes the interface larger than callers need and leaves an escape hatch around intent-level view transitions.

## Solution

Make the PhotoWorkspace interface express its authoritative view state once, keep snapshots immutable, and test visibility through real intent-level operations.

## User Stories

1. As a maintainer, I want one authoritative way to determine the active Photo Workspace view.
2. As a maintainer, I want callers to use named workspace intents instead of injecting arbitrary visibility.
3. As a test author, I want to set up workspace state through the same interface as production callers.
4. As a TAGGER user, I want this internal simplification to preserve selection, filtering, and search behavior.

## Implementation Decisions

- Retain the view-mode enumeration as the authoritative logical view representation.
- Remove or confine redundant derived flags when all callers can derive them from the authoritative state.
- Replace the general visibility escape hatch with intent-level test setup or a narrowly named test seam where necessary.
- Do not expose mutable collections or move Qt concerns into PhotoWorkspace.

## Testing Decisions

- Update pure workspace tests to assert behavior through named operations.
- Preserve search, filtering, selection-repair, and stale-result coverage.
- Add regression coverage for every removed compatibility field or operation before deleting it.

## Out of Scope

- Altering search or IPTC-empty behavior.
- Broad model redesign beyond reducing the present interface ambiguity.

## Further Notes

This is suitable for direct ticketing after a short caller inventory; no grilling is currently required.