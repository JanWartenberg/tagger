# 03 — Propagate Tags from Assessed Candidates

Status: needs-triage
Category: feature
Priority: medium
Milestone: M8 — Duplicate candidate review and tag propagation
Blocked by: 02

## Goal

Turn a positively assessed candidate group into an explicit, confirmed plan that
merges canonical source tags into selected targets through the existing reliable
tag-mutation workflow.

## Scope

- Refresh and validate source IPTC tags before confirmation.
- Wait for pending source mutation intent to resolve rather than copying
  optimistic UI state.
- Preview exact additions and retained target tags.
- Confirm source, targets, additions, and current backup setting.
- Submit additions through the existing tag-mutation coordinator.
- Keep per-target successful, failed, pending, and retryable outcomes visible in
  duplicate review.

## Acceptance Criteria

- [ ] No metadata changes occur before explicit confirmation.
- [ ] Empty or unreadable source IPTC tags cannot produce a propagation plan.
- [ ] Existing target tags are retained and source tags are merged
      case-insensitively as additions.
- [ ] A plan cannot include paths outside its assessed scan result or use its
      source as a target.
- [ ] Stale source metadata or changed candidate evidence requires reassessment
      rather than silently applying the old plan.
- [ ] Writes preserve canonical IPTC/XMP behavior, keyword limits, and backup
      settings.
- [ ] Partial failure retains successful writes and exposes normal failed/retry
      state only for failed targets.
- [ ] Workspace or review navigation cannot redirect an old plan to new paths.
- [ ] Tests cover confirmation cancellation, source refresh, pending source
      intent, merge behavior, stale plans, partial success, and retry.

## Out of Scope

- Replacing target tags.
- Automatic propagation without assessment.
- File deletion, moves, or duplicate consolidation.
- Alternative detectors.

## Design Reference

See the accepted [design direction](../design-notes.md).
