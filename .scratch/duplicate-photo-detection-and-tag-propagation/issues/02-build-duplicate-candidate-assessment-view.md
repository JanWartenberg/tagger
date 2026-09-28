# 02 — Build Duplicate-Candidate Assessment View

Status: completed
Category: feature
Priority: medium
Milestone: M8 — Duplicate candidate review and tag propagation
Blocked by: None

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

- [x] Opening duplicate review does not start a scan or mutate files.
- [x] Starting a scan captures its selected scope and detector identity.
- [x] Cancelled or superseded scan results cannot replace the active result.
- [x] Candidate groups remain stable while they are reviewed.
- [x] The UI calls groups candidates and shows the evidence method explicitly.
- [x] Read failure is distinguishable from a confirmed empty IPTC tag list.
- [x] A source cannot simultaneously be a target.
- [x] A photo series can be assessed member by member without treating the whole
      timestamp group as automatically accepted.
- [x] Keyboard interaction does not trigger normal tagging commands accidentally.
- [x] Tests cover scan start/cancel, stale completion, rendering evidence, source
      and target rules, and preservation of normal tagging state.
- [x] The candidate representation has a maintainer-approved visual hierarchy
      that makes groups, members, evidence, tag state, source, and targets clear.

## Acceptance Feedback — Candidate Representation

The original grid-like result was confusing because it did not explain what the
findings meant or what action could follow. A replacement is ready for maintainer
review:

- candidate groups form a compact horizontal queue;
- clicking a group makes it active in a large assessment area;
- the active group shows image previews, paths, timestamp evidence and field
  provenance, and readable, empty, or unknown canonical IPTC tag state;
- the view explains that candidates are evidence rather than confirmed
  duplicates;
- an optional filter hides only groups whose members all have confirmed-empty
  IPTC tag lists; unreadable tag state is not treated as empty;
- source and target choices preview the coming propagation workflow;
- Ignore removes a group only from the current scan and states that the choice is
  not persisted; and
- a disabled Apply tags button shows where ticket 03 continues the workflow
  without crossing the read-only ticket boundary.

Accepted by the maintainer. Minor visual refinements may follow separately if
real use identifies them, but they do not block this ticket.

## Out of Scope

- Writing or copying tags.
- Alternative detectors.
- Deleting, moving, or consolidating files.

## Prototype

A throwaway navigation and assessment-view prototype is available on branch
`prototype/duplicate-review-ui` at
`prototype/duplicate-review-navigation-variants.html`. It compares a status-bar
view selector, a hover/focus edge drawer, and a compact title-bar menu without
changing the tagging workspace.

Selected direction: a compact `Views` menu in the existing status bar. The edge
drawer was rejected as tricky, and a separate application-menu row was rejected
because it consumes vertical workspace. The same branch contains a runnable Qt
navigation shell using a `QStackedWidget`; it preserves the Photo Workspace and
blocks normal tagging commands while duplicate review is active.

Branch policy: continue all duplicate-detection work on
`prototype/duplicate-review-ui` for now. Keep `main` at the original accepted
TAGGER baseline until an explicit integration decision is made.

Implementation progress:

- Scope preparation automatically snapshots either the active index database or
  a selected subfolder in the background and displays the frozen path count.
  Detector scanning remains explicit, with an estimated-work explanation plus
  visible progress and cancellation.
- Explicit detector runs report progress, support cancellation, and reject stale
  completion from cancelled or superseded scans.
- Stable candidate groups show timestamp evidence, canonical IPTC availability,
  confirmed-empty state, and metadata read failures.
- Each group records one explicit source and independent targets; a source cannot
  remain selected as a target, and a sole tagged member is labelled as suggested.
- Opening review, preparing scopes, scanning, and assessment remain read-only.
- Ruff and the full 289-test offscreen regression suite pass.
- The accepted candidate representation follows the selected horizontal-queue
  prototype; focused UI coverage verifies
  queue navigation, preview surfaces, confirmed-empty filtering, current-scan
  Ignore, and the disabled propagation affordance.
- Duplicate-review controls expose contextual keyboard and command routes aligned
  with TAGGER's Vim-style navigation: `j/k` groups, `h/l` photos, `s` source, `t`
  target, `e` empty-group filtering, `x` ignore, and `Space s` scan. Tooltips
  advertise each available route; Apply tags advertises its reserved future keys.
- All-zero capture-date placeholders are treated as unusable; the detector falls
  back to `EXIF:CreateDate` or omits the photo from timestamp groups.

## Design Reference

See the accepted [design direction](../design-notes.md).
