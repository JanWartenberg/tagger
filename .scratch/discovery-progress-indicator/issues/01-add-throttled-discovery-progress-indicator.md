# 01 — Add Throttled Discovery Progress Indicator

Status: wontfix
Category: feature
Priority: low
Milestone: M2 — Reliable, scalable index operations
Blocked by: None

## Goal

Make large background photo discoveries visibly progress without delaying or replacing the current loading behavior.

## Required Triage Before Implementation

- Resolve the progress contract, cadence, and UI wording.
- Define current/stale event acceptance for replacement and additive discoveries.
- Confirm the count's inclusion rule.

## Comments

Created from `BACKLOG.md`; the completed background-discovery work deliberately deferred this follow-up.

Tracker cleanup: the Aug. 4 responsive loading animation is indeterminate feedback only. It complements this ticket's proposed discovered-photo count and does not satisfy or supersede it.

Closed as `wontfix`: the existing folder-loading feedback plus DB-index refresh progress is sufficient. A third, separate folder-discovery count is not useful enough to justify its UI and event-lifecycle complexity.
