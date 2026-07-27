# Main Window Coordinator Decomposition

Status: completed
Priority: high

## Problem Statement

The MainWindow module combines widget construction, input routing, Photo Workspace rendering, index orchestration, metadata loading, tag mutation queueing, cache management, preview handling, and dialogs. This weakens locality: unrelated changes converge on one large module and require broad context to modify safely.

## Solution

Extract tag-mutation queueing and lifecycle coordination behind one Qt-free deep module with a small explicit interface. Preserve all user-visible behavior and existing public entrypoints; MainWindow remains the Qt adapter for cache, index, and widget updates.

## User Stories

1. As a maintainer, I want tag-mutation queueing and stale-work rules to be understandable without reading widget code.
2. As a maintainer, I want tag mutation coordination to be testable without constructing a full window.
3. As a TAGGER user, I want this structural work to preserve commands, shortcuts, focus behavior, and responsiveness.

## Implementation Decisions

- Preserve the existing Photo Workspace seam; do not create a second owner for its state.
- Extract one Qt-free Tag Mutation Coordinator. It owns serialized queueing, pending/failed mutation lifecycle, workspace-generation stale-work rejection, and discarding queued mutations for departed photos.
- The coordinator composes the existing intent and confirmed-state rules. It publishes immutable lifecycle facts; it does not own widget rendering, the MainWindow metadata cache, index updates, footer wording, focus, or scroll behavior.
- MainWindow forwards user intent and confirmed metadata facts to the coordinator, then renders its emitted lifecycle facts and submits confirmed states to the index.
- Accept the mutation executor and background runner at the coordinator seam so direct tests use deterministic fakes rather than constructing widgets or patching unrelated constructors.
- Keep Qt-only concerns in the Qt adapter and external process/database work behind existing adapters.

## Testing Decisions

- Preserve Photo Workspace pure tests and offscreen adapter characterization tests.
- Add direct Tag Mutation Coordinator tests using a deterministic runner and fake mutation executor.
- Keep offscreen tests at the MainWindow seam for observable pending/failed indicators, retries, index submission, and stale completion behavior.
- Test public behavior and result contracts, not private Qt fields or method forwarding.

## Out of Scope

- A framework rewrite, package hierarchy migration, or changes to user-facing behavior.
- Input/key routing extraction, selected-photo metadata loading, preview lifecycle, or other MainWindow responsibilities. Reassess those only after this coordinator extraction is implemented and reviewed.
- Combining this work with unrelated feature development.

## Further Notes

The initial extraction for background folder discovery and index I/O is complete in `services/background_coordinator.py`. This follow-up is deliberately limited to a Tag Mutation Coordinator. Input routing, selected-photo metadata loading, and preview lifecycle are deferred candidates, not implementation commitments; decide whether further refactoring is worthwhile only after this extraction is implemented and assessed.