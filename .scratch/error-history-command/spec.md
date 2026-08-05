# Error History Command

Status: completed
Priority: low

## Problem Statement

Transient footer feedback can hide earlier background-operation failures during a session.

## Desired Outcome

Record tool errors with timestamps for one application session and expose them through an `:errors` command.

## Resolved Policy

- A **Session error** records an operational failure from discovery, index, search, filter, ExifTool, or file-action work. It also records failures already shown in a modal dialog.
- Expected input-validation and workflow-state guidance is not an error-history event. This includes unknown commands, invalid queries, and messages such as no selected photo.
- A failed tag mutation creates one aggregate error for the mutation, rather than one entry per affected photo.
- Each entry has a local `HH:MM:SS` timestamp, a source label, and the user-facing error detail.
- The history is in reverse chronological order, holds at most 100 entries, and drops the oldest entry when full.
- `:errors` is listed in the command catalogue and opens a read-only dialog. Its empty state is `No errors in this session.`
- There is no clear command and no persistence. A new Application session starts with an empty history.

## Constraints

- Existing footer and modal feedback remains unchanged; recording an error supplements it.
- Do not persist error history across application restarts.

## Completion

Implemented as a bounded, session-only `SessionErrorHistory` with the `:errors` action-catalogue command. Existing footer and modal feedback remains unchanged.

## Testing Requirements

- Characterize qualifying and excluded messages, including aggregate tag-mutation failures.
- Cover reverse ordering, the 100-entry bound, the empty state, and `:errors` command wiring offscreen.
