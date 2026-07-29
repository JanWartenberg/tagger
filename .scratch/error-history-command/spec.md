# Error History Command

Status: needs-triage
Priority: low

## Problem Statement

Transient footer feedback can hide earlier background-operation failures during a session.

## Desired Outcome

Record tool errors with timestamps for one application session and expose them through an `:errors` command.

## Open Triage Decisions

- Which failures qualify as recorded tool errors and their user-facing detail.
- Ordering, empty-state wording, and command-list presentation.
- Retention, bounded history, and interaction with normal footer feedback.

## Constraints

- Keep the initial background discovery/index-I/O scope unchanged: it continues to report errors non-modally in the footer.
- Do not persist error history across application restarts unless separately decided.
