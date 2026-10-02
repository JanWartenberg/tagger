# 02b — Make Duplicate review Scan setup collapsible

Status: needs-info
Category: feature
Priority: medium
Milestone: M9 — Repeatable real-file acceptance
Blocked by: maintainer Windows visual acceptance

## Goal

After a scan, let the user collapse Scan setup to reclaim space for candidate
groups and candidate photos. This is a separate follow-up to accepted M8.

## Acceptance

- [x] Scan setup has an explicit collapse/expand control available after scanning.
- [x] Collapsing preserves scope, detector, results and review selections.
- [x] Expanded controls remain available for subsequent scans.
- [x] Candidate review receives the freed space without hiding navigation/status.
- [x] Keyboard access and current-view help remain consistent.
- [ ] Maintainer confirms Windows layout/focus at the usual window size.

## Open decision

Automatic collapse after completion versus user-triggered collapse is not specified.
Use a user-triggered control unless the maintainer explicitly requests automation;
no persisted preference is required.

## Delivery

Implemented the user-triggered header toggle (`Alt+U`, `:togglescansetup`). No
automatic collapse or persisted setting. Scope focus (`Alt+S`) and starting a new
scan reopen the setup so controls/progress remain accessible. Splitter sizes are
restored on expansion; candidate/status navigation stays outside the hidden panel.

Public Qt tests verify reclaimed review height, preserved scope/source/target
choices, keyboard access, focus recovery, subsequent scans and current-view help.
Native Windows visual confirmation is still required.
