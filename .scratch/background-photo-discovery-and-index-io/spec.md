# Background Photo Discovery and Index I/O

Status: needs-triage
Priority: high

## Problem Statement

Opening or dropping a large Photo Workspace can perform filesystem discovery and index database work on the Qt UI thread. Users can experience an unresponsive window while images are found, checked, or indexed.

## Solution

Keep the Photo Workspace responsive while photos are discovered and index state is queried or persisted. The Qt adapter should receive completed results and render them; filesystem traversal, metadata reads, and SQLite work must not block interaction.

## User Stories

1. As a TAGGER user, I want to open a folder containing thousands of photos without the window freezing.
2. As a TAGGER user, I want drag-and-drop of a folder to remain responsive while its photos are discovered.
3. As a TAGGER user, I want visible feedback while long discovery or indexing work is pending.
4. As a TAGGER user, I want switching to another folder to prevent old work from changing my current Photo Workspace.
5. As a maintainer, I want all potentially slow filesystem and index work outside the UI thread.

## Implementation Decisions

- Preserve the Photo Workspace as the authority for membership, selection, and visibility.
- Keep widget creation, rendering, focus, scroll anchoring, and signal handling in the Qt adapter.
- Move filesystem discovery and index reads/writes that can scale with the number of photos to background work.
- Return immutable completion results to the UI thread; UI callbacks apply results only when they still belong to the active workspace/root.
- Define progress and cancellation/staleness handling before implementation.

## Testing Decisions

- Test discovery/index coordination through a fake discovery source and fake index at the highest non-Qt seam available.
- Test the Qt adapter offscreen with controlled asynchronous completions; assert current-workspace rendering and stale-result rejection, not thread internals or timing.
- Cover a large synthetic path collection without real images or ExifTool.

## Out of Scope

- Changing index schema, search syntax, or Photo Workspace behavior.
- Completing the deferred reverse-search product work.

## Further Notes

Grilling is required before tickets: settle progress UX, cancellation semantics, result batching, and whether index writes are serialized or coalesced.