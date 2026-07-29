# Discovery Progress Indicator

Status: needs-triage
Priority: low

## Problem Statement

Folder and dropped-directory discovery shows only indeterminate loading feedback, so users cannot tell how much of a large discovery has completed.

## Desired Outcome

Show a throttled running count of discovered photos during background discovery without making it a prerequisite for the existing indeterminate loading behavior.

## Open Triage Decisions

- Update cadence, wording, and whether replacement and additive discovery use distinct feedback.
- Event shape and stale-result handling through `BackgroundCoordinator`.
- Whether counts include only accepted image paths or every visited path.

## Constraints

- Filesystem traversal remains off the Qt UI thread.
- Keep the current loading presentation usable if incremental count reporting is unavailable or fails.
