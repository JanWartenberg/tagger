# 02 — Build Duplicate-Candidate Assessment View

Status: needs-triage
Category: feature
Priority: medium
Milestone: M8 — Duplicate candidate review and tag propagation
Blocked by: 01

## Goal

Add a dedicated in-app view that runs a named detector, displays stable candidate
groups and evidence, and records explicit source/target assessment without
changing metadata.

## Scope

- Choose database or subfolder scan scope.
- Default the method to `SameCaptureTimestampDetector`.
- Show scope size before an explicit scan starts.
- Run scanning in the background with progress and cancellation.
- Present groups, paths, timestamp evidence, canonical IPTC tag availability,
  and per-photo read failures.
- Allow exactly one source and zero or more targets per assessed group.
- Suggest a sole tagged member as source while requiring positive user
  assessment before propagation can be prepared.
- Preserve normal tagging selection, filters, and indexed-search state when
  entering or leaving review.

## Acceptance Criteria

- [ ] Opening duplicate review does not start a scan or mutate files.
- [ ] Starting a scan captures its selected scope and detector identity.
- [ ] Cancelled or superseded scan results cannot replace the active result.
- [ ] Candidate groups remain stable while they are reviewed.
- [ ] The UI calls groups candidates and shows the evidence method explicitly.
- [ ] Read failure is distinguishable from a confirmed empty IPTC tag list.
- [ ] A source cannot simultaneously be a target.
- [ ] A photo series can be assessed member by member without treating the whole
      timestamp group as automatically accepted.
- [ ] Keyboard interaction does not trigger normal tagging commands accidentally.
- [ ] Tests cover scan start/cancel, stale completion, rendering evidence, source
      and target rules, and preservation of normal tagging state.

## Out of Scope

- Writing or copying tags.
- Alternative detectors.
- Deleting, moving, or consolidating files.

## Design Reference

See the accepted [design direction](../design-notes.md).
