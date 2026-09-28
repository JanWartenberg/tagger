# 04 — Remember Ignored Duplicate Candidates

Status: needs-triage
Category: feature
Priority: low
Milestone: M-Future — Unscheduled opportunities
Blocked by: 02

## Goal

Allow users to ignore a duplicate-candidate group without being shown the same
candidate again in a later scan.

## Scope

- Record an explicit Ignore decision for a candidate group.
- Define stable identity and lifecycle for ignored candidates.
- Exclude remembered candidates from later review without hiding new evidence.
- Provide a way to inspect, restore, or clear ignored candidates.

## Acceptance Criteria

- [ ] Ignoring a candidate removes it from the active review list.
- [ ] A later scan does not automatically re-present the same ignored candidate.
- [ ] New or changed candidate evidence is not silently suppressed.
- [ ] Users can inspect and undo ignored-candidate decisions.
- [ ] Tests cover persistence, identity changes, restore, and clear behavior.

## Out of Scope

- Automatically confirming duplicates.
- Deleting, moving, or consolidating files.
- Tag propagation.
