# 01 — Implement Duplicate-Candidate Detection Foundation

Status: ready-for-agent
Category: feature
Priority: medium
Milestone: M8 — Duplicate candidate review and tag propagation
Blocked by: None

## Goal

Introduce the exchangeable, Qt-free detector boundary and implement
`SameCaptureTimestampDetector` as the default method over immutable database or
subfolder path scopes.

This ticket produces read-only candidate results. It does not build the review UI
or write tags.

## Interface Direction

Create a focused detection module whose public model represents:

- a named detection method;
- one immutable scan request with scan identity and paths;
- stable candidate groups and member evidence;
- progress and cancellation; and
- per-photo scan errors.

Keep scope acquisition outside the detector. Add narrow adapters that snapshot:

- all photo paths in the current `PhotoIndex`; and
- supported photo paths discovered below a selected subfolder.

Do not introduce a dynamic plugin framework. Tests must be able to substitute a
detector through the same small internal interface used by later review code.

## Repository Integration Notes

- Add a public, deterministically ordered `PhotoIndex` operation for snapshotting
  every indexed photo path; do not expose or pass around its SQLite connection.
- Reuse `services.photo_discovery.FileSystemPhotoDiscovery` and the shared
  supported-extension policy for subfolder discovery rather than adding another
  recursive filesystem walk. Normalize, deduplicate, and freeze the discovered
  paths before constructing the request.
- Put detector policy and result models in a Qt-free module. Keep ExifTool access
  behind a narrow batch-reader seam so pure tests can supply per-path metadata
  and failures without starting a process.
- The production batch reader must distinguish a missing/unreadable record from
  a readable photo with no capture timestamp. Do not infer both cases from a
  missing `read_keywords_many` entry.
- Compare stripped ExifTool values from `EXIF:DateTimeOriginal`, falling back only
  when absent to `EXIF:CreateDate`. Do not use XMP dates, calendar-day projection,
  fuzzy windows, or timezone/subsecond synthesis.
- Represent cancellation as a non-complete outcome (or a dedicated exception),
  never as a normal complete result. Progress is monotonic in processed paths
  and reaches the immutable request size only for a completed scan.

## Default Detector Policy

`SameCaptureTimestampDetector`:

1. reads metadata in bounded batches;
2. uses `EXIF:DateTimeOriginal` when available;
3. otherwise uses `EXIF:CreateDate` and records that provenance;
4. groups equal effective timestamps;
5. omits photos without a usable timestamp from candidate groups while reporting
   their outcome; and
6. returns only groups with at least two members.

The result calls these groups candidates, not confirmed duplicates. Do not add
camera IDs, pixel hashing, perceptual hashing, fuzzy time matching, or confidence
scores in this ticket.

## Acceptance Criteria

- [ ] Detection policy and result models import no Qt.
- [ ] The detector has a stable user-visible name and machine identity.
- [ ] Candidate members preserve their path, compared timestamp, and source field.
- [ ] Group and member ordering is deterministic.
- [ ] Database scope snapshots all indexed photo paths through a public
      `PhotoIndex` operation without exposing its SQLite connection.
- [ ] Subfolder scope recursively discovers only supported photo files.
- [ ] The scan operates on the immutable path snapshot supplied at start.
- [ ] Metadata reads use bounded batches and expose progress.
- [ ] Cancellation is checked between batches and a cancelled scan cannot return
      publishable complete results.
- [ ] One unreadable or missing photo does not prevent other candidate groups.
- [ ] Pure tests cover DateTimeOriginal grouping, labelled CreateDate fallback,
      timestamp-less photos, bursts with more than two members, deterministic
      ordering, scope isolation, partial read failure, progress, and cancellation.
- [ ] Ruff passes for modified Python files and the full test suite remains green.

## Out of Scope

- Candidate assessment UI.
- Source and target selection.
- Metadata writes or tag propagation.
- `SameImageUniqueIdDetector`, `SameDecodedPixelsDetector`, and
  `PerceptuallySimilarDetector`.
- Persistent scan results or fingerprint caches.

## Design Reference

See the accepted [design direction](../design-notes.md).
