# Duplicate Photo Detection and Tag Propagation

Status: completed
Priority: medium
Milestone: M8 — Duplicate candidate review and tag propagation

## Goal

Let a user run a named duplicate-candidate detector over the indexed photo
database or a selected subfolder, assess the resulting candidate groups, and
explicitly copy tags from one chosen source to chosen targets.

Detection supplies candidates for human assessment; it does not assert that the
files are duplicates and never changes metadata by itself.

## Accepted Product Direction

- The default and initial method is `SameCaptureTimestampDetector`.
- It groups exact effective capture timestamps, preferring
  `EXIF:DateTimeOriginal` and using a labelled `EXIF:CreateDate` fallback.
- Photo series and bursts may appear as candidate groups and are resolved by the
  user in the assessment UI.
- Scope selection is independent from detection. Initial scopes are the entire
  current index database and a user-selected subfolder.
- Review uses a dedicated view inside TAGGER, not a Photo Workspace filter mode.
- The user explicitly chooses one readable, settled, non-empty source. Every
  readable, settled, confirmed-empty target is preselected and may be deselected
  individually.
- Propagation copies the source's canonical tags only into selected empty
  targets; images with existing or unknown tags are ineligible.
- Help lists only the current view's commands/shortcuts and explains Edit-mode
  keys. Photo navigation visibly highlights and scrolls focused cards, and full
  paths remain readable in dark themes. Scan shortcuts work with window focus
  after command execution, not just with focus inside the review view.

The accepted design is detailed in [design-notes.md](design-notes.md).

## Exchangeable Detection Method

The detector boundary accepts immutable photo paths and returns candidate groups,
method-specific evidence, and per-photo errors. It does not own scope selection,
review state, or writes. The initial implementation needs an internal seam, not
a public plugin framework.

Explicit alternatives reserved for later are:

- `SameImageUniqueIdDetector`
- `SameDecodedPixelsDetector`
- `PerceptuallySimilarDetector`

They are not part of the initial implementation.

## Workflow

1. Choose database or subfolder scope and review its path count.
2. Run the selected detector in the background.
3. Present stable candidate groups and their evidence.
4. Show canonical IPTC tag availability for every member.
5. Let the user assess the candidate, choose a valid source, and adjust the
   preselected eligible empty targets.
6. Preview the exact copied tags and selected targets and request confirmation.
7. Apply the confirmed copy through the existing tag-mutation workflow.
8. Advance review while a compact row reports pending, successful, failed, and
   retryable outcomes per target.

## Constraints

- Discovery and metadata reads must stay off the Qt UI thread.
- A scan is explicit, cancellable, and bound to an immutable scope snapshot.
- Cancelled or superseded scans cannot publish active results.
- Missing or unreadable photos do not discard otherwise valid results.
- No file changes occur before explicit confirmation.
- Source and target tags must be refreshed before confirmation and represent
  confirmed file state rather than pending intent. The source must be non-empty;
  every target must be confirmed empty.
- Preserve canonical IPTC/XMP behavior, keyword limits, backup settings,
  pending/failed mutations, retries, and Session errors.
- Partial propagation failures must not hide successful writes.

## Delivery

Implementation is split into detection foundation, assessment UI, and tag
propagation tickets. The simple end-to-end workflow takes priority over more
sophisticated matching methods.

## Delivery status

- 2026-09-23: Detection foundation was accepted in commit `c39d6a9`.
- Duplicate assessment, Add Folder and tag propagation are accepted. The
  maintainer closed ticket 03 after a Windows suite pass, explicit AT-02 PASS,
  cancellation evidence and correct real-file copying/backups. Remaining manual
  checks were explicitly waived, not recorded as passed; see ticket 03 for the
  precise evidence and gaps. A [real-file integration subproject](../windows-integration-suite/spec.md)
  replaces repeated manual acceptance. The collapsible Scan setup request is
  tracked separately as ticket 02b. Integration of `prototype/duplicate-review-ui`
  into `main` still requires a separate explicit decision.
