# Main Window Coordinator Decomposition

Status: needs-triage
Priority: high

## Problem Statement

The MainWindow module combines widget construction, input routing, Photo Workspace rendering, index orchestration, metadata loading, tag mutation queueing, cache management, preview handling, and dialogs. This weakens locality: unrelated changes converge on one large module and require broad context to modify safely.

## Solution

Reduce MainWindow to a Qt-facing adapter by moving coherent non-widget coordination responsibilities behind small, deep modules with explicit interfaces. Preserve all user-visible behavior and existing public entrypoints.

## User Stories

1. As a maintainer, I want Photo Workspace rendering and intent forwarding to be understandable without reading index or mutation code.
2. As a maintainer, I want index coordination to change without editing keyboard routing or widget construction.
3. As a maintainer, I want tag mutation coordination to be testable without constructing a full window.
4. As a maintainer, I want input routing to evolve without coupling it to metadata operations.
5. As a TAGGER user, I want this structural work to preserve commands, shortcuts, focus behavior, and responsiveness.

## Implementation Decisions

- Preserve the existing Photo Workspace seam; do not create a second owner for its state.
- Identify cohesive coordinator modules by responsibility rather than extracting one method per class.
- Candidate responsibilities include index coordination, tag-mutation coordination, and input routing; choose seams based on caller leverage and locality.
- Make dependencies accepted at seams rather than requiring tests to patch constructors in unrelated modules.
- Keep Qt-only concerns in the Qt adapter and external process/database work behind their existing or improved seams.

## Testing Decisions

- Preserve Photo Workspace pure tests and offscreen adapter characterization tests.
- Add direct tests at each chosen coordinator interface using fakes for external systems.
- Test public behavior and result contracts, not private Qt fields or method forwarding.

## Out of Scope

- A framework rewrite, package hierarchy migration, or changes to user-facing behavior.
- Combining this work with unrelated feature development.

## Further Notes

Grilling is required before tickets: choose the first extraction, define its interface, and set a narrow migration boundary. This spec should be implemented incrementally, not as a single rewrite.