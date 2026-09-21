# Duplicate Photo Detection and Tag Propagation

Status: ready-for-agent
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
- The user explicitly chooses one source and one or more targets.
- Propagation merges source tags into each target; it does not replace existing
  target tags.

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
5. Let the user assess the candidate and select a source and targets.
6. Preview merged tag additions and request confirmation.
7. Apply confirmed additions through the existing tag-mutation workflow.
8. Report success or failure per target and preserve existing retry semantics.

## Constraints

- Discovery and metadata reads must stay off the Qt UI thread.
- A scan is explicit, cancellable, and bound to an immutable scope snapshot.
- Cancelled or superseded scans cannot publish active results.
- Missing or unreadable photos do not discard otherwise valid results.
- No file changes occur before explicit confirmation.
- Source tags must be refreshed before confirmation and represent confirmed file
  state rather than pending intent.
- Preserve canonical IPTC/XMP behavior, keyword limits, backup settings,
  pending/failed mutations, retries, and Session errors.
- Partial propagation failures must not hide successful writes.

## Delivery

Implementation is split into detection foundation, assessment UI, and tag
propagation tickets. The simple end-to-end workflow takes priority over more
sophisticated matching methods.
