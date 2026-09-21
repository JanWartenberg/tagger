# Duplicate Detection and Tag Propagation — Accepted Design Direction

Status: accepted for incremental implementation.

## Purpose

TAGGER will treat duplicate detection as a way to produce review candidates, not
as proof that files are duplicates. A person reviews each candidate group before
any tags are copied.

This keeps the first detector deliberately simple while allowing a different
method to replace or complement it later.

## 1. Detection boundary

A detector has a clear, user-visible name. It accepts an immutable collection of
photo paths and returns stable candidate groups with method-specific evidence and
per-photo errors.

Detection does not:

- choose the scan scope;
- decide whether a candidate is truly a duplicate;
- choose tag sources or targets;
- mutate metadata; or
- depend on Qt.

The initial implementation needs a small internal interface, not a generalized
plugin system. Review and propagation must depend on the detector result model,
not on timestamp-specific internals.

## 2. Default method: SameCaptureTimestampDetector

`SameCaptureTimestampDetector` is the default and the only initial detector.

It groups photos that report the same effective capture timestamp:

1. use `EXIF:DateTimeOriginal` when present;
2. otherwise use `EXIF:CreateDate` and label that fallback in the evidence;
3. omit a photo from timestamp groups when neither value is usable; and
4. return only groups with at least two members.

The detector preserves each member's timestamp value and field provenance for
the review UI. It makes no claim that a group is an exact duplicate. In
particular, a photo series or burst can legitimately produce one candidate group
and is resolved during human assessment.

The first version does not add camera-model rules, camera IDs, pixel decoding,
confidence scores, or fuzzy timestamp windows. Timestamp parsing and
normalization should be only as strict as necessary to compare the ExifTool
values consistently; it must not silently invent precision or timezone data.

## 3. Explicit later alternatives

These names reserve clear alternative meanings without putting them in the first
implementation:

- `SameImageUniqueIdDetector`: candidate groups based on a shared standard image
  unique ID when available.
- `SameDecodedPixelsDetector`: exact groups based on a documented decoded-pixel
  representation.
- `PerceptuallySimilarDetector`: weak candidates for resized, recompressed, or
  edited variants that always require human assessment.

Adding one of these detectors must not require replacing the scan, review, or tag
propagation workflow.

## 4. Scan scope

Scope selection is separate from detection. The first product workflow supports:

- all photo paths in the current index database; or
- supported photos discovered below a user-selected subfolder.

The chosen scope is captured as immutable paths when the scan starts. Filters and
selection in the normal Photo Workspace do not silently narrow it. The review UI
must state the scope and number of paths before starting.

A future current-workspace scope can be added without changing the detector.

Filesystem discovery and metadata reads run in the background. Missing,
unreadable, or changed paths are reported without discarding successful groups.
Cancellation or a superseding scan prevents old results from becoming active.

## 5. Review workflow

Use a dedicated duplicate-review view inside TAGGER rather than overloading a
Photo Workspace filter mode.

1. User chooses database or subfolder scope.
2. User chooses a named detector; `SameCaptureTimestampDetector` is selected by
   default.
3. User explicitly starts the background scan.
4. TAGGER displays candidate groups and the detector's evidence.
5. TAGGER shows confirmed canonical IPTC tags for each member; metadata read
   failures are `unknown`, not `no tags`.
6. User assesses a group and explicitly chooses one source and one or more
   targets.
7. TAGGER previews the tag additions and asks for confirmation.
8. Confirmed changes use the existing tag-mutation workflow.

A source is a single choice and targets are independent checkboxes. A source
cannot also be a target. A sole tagged member may be suggested as the source,
but no candidate is accepted automatically. Existing target tags are retained;
source tags are merged as additions rather than replacing target tags.

Returning to normal tagging preserves its selection, filters, and search state.
Review source/target choices remain local to duplicate review.

## 6. Safety and lifecycle

- A scan never changes metadata.
- Filesystem and metadata work stays off the Qt UI thread.
- Every active result carries scan identity, detector identity, and scope.
- Starting another scan invalidates the previous active result.
- Source tags are refreshed before confirmation; pending source mutations must
  resolve before copying confirmed file truth.
- A propagation plan records the assessed group, source, targets, and intended
  additions. It cannot be applied to paths outside its scan result.
- Writes use existing canonical IPTC/XMP behavior, backup settings, keyword
  limits, pending/failed state, retry behavior, and Session errors.
- Partial success remains visible: successful targets stay successful and failed
  targets retain the normal retry semantics.

## 7. Delivery sequence

1. **Detection foundation:** detector/result model, database and subfolder scope
   adapters, `SameCaptureTimestampDetector`, cancellation/progress, and pure
   tests.
2. **Assessment UI:** dedicated review view populated from stable candidate
   results, with evidence and source/target selection.
3. **Propagation:** additions preview, confirmation, fresh-source validation, and
   submission through the existing tag-mutation coordinator.
4. **Later detectors:** add only when actual usage justifies them.

This sequence intentionally prioritizes an end-to-end review workflow over a
more sophisticated first detector.
