# 02b — Make Duplicate review Scan setup collapsible

Status: ready-for-agent
Category: feature
Priority: medium
Milestone: M9 — Repeatable real-file acceptance

## Goal

After a scan, let the user collapse Scan setup to reclaim space for candidate
groups and candidate photos. This is a separate follow-up to accepted M8.

## Acceptance

- [ ] Scan setup has an explicit collapse/expand control available after scanning.
- [ ] Collapsing preserves scope, detector, results and review selections.
- [ ] Expanded controls remain available for subsequent scans.
- [ ] Candidate review receives the freed space without hiding navigation/status.
- [ ] Keyboard access and current-view help remain consistent.

## Open decision

Automatic collapse after completion versus user-triggered collapse is not specified.
Use a user-triggered control unless the maintainer explicitly requests automation;
no persisted preference is required.
