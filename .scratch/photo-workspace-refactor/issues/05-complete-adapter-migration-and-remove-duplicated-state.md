# Complete the Photo Workspace adapter migration

Status: ready-for-agent
Blocked by: 04

## Goal

Finish the behavior-preserving migration and remove superseded Photo Workspace state and rules from `MainWindow`.

## Acceptance criteria

- `MainWindow` is a thin Qt adapter: it forwards intent, schedules external work, renders snapshots, and owns Qt-only state (focus, scrollbars, widgets, workers, timers, signal wiring, dialogs).
- `PhotoWorkspace` owns all state named in the refactor spec: identities, ordering, mode, visibility, ordered selection, active-photo rule, logical restoration state, filter progress, batches, and stale-result acceptance.
- The old parallel state fields and duplicate transition logic are removed rather than retained as fallbacks.
- Existing launcher, controls, keyboard/mouse behavior, commands, persistence formats, ExifTool behavior, and status/error behavior remain materially unchanged.
- New and modified Python passes Ruff without broadly reformatting unrelated code.
- Pure tests pass in Linux; Windows offscreen integration acceptance passes.

## Out of scope

- The deferred backlog items: frozen-snapshot filtering, complete reverse search, tag-mutation redesign, action-dispatch redesign, and broad cleanup.
