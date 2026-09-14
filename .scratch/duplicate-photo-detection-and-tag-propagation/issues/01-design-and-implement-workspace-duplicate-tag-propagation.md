# 01 — Detect Workspace Duplicates and Offer Tag Propagation

Status: needs-triage
Category: feature
Priority: medium
Blocked by: .scratch/loading-saving-indexing-performance/issues/01-profile-and-optimize-core-workflows.md

## Problem

Photos added to one Photo Workspace may contain duplicate images. A duplicate
may already have useful tags while its copies do not, but TAGGER currently does
not identify these groups or offer tag propagation.

## Goal

Scan the current Photo Workspace for duplicate-photo groups, identify tagged
members, and offer an explicit action to copy tags from a selected source photo
to the other duplicates.

## Proposed Workflow

1. User starts a duplicate scan for the current Photo Workspace.
2. TAGGER performs date/timestamp and/or payload matching in a background task.
3. TAGGER presents duplicate groups and indicates which members have tags.
4. User selects a tagged source and confirms propagation to selected untagged or
   duplicate members.
5. TAGGER applies the changes through the existing reliable tag-mutation path
   and reports per-photo success or failure.

## Acceptance Criteria

- [ ] The scan is explicitly started and limited to the files in the current
      Photo Workspace snapshot.
- [ ] Duplicate groups are reported with the matching evidence for each group.
- [ ] Capture timestamp and payload matching follow a documented policy agreed
      during triage; ambiguous matches are not silently treated as identical.
- [ ] The result identifies which group members have canonical IPTC keywords.
- [ ] The user can choose a tagged source and explicitly confirm copying tags to
      other members of the group.
- [ ] Tag propagation preserves the canonical IPTC/XMP behavior and existing
      backup settings.
- [ ] Partial failures retain the existing pending/failed/retry semantics and
      do not hide successful writes.
- [ ] Filesystem, hashing, and metadata operations remain off the Qt UI thread.
- [ ] Workspace changes or stale scan results cannot apply propagation to a new
      workspace accidentally.
- [ ] Tests cover duplicate grouping, timestamp/payload evidence, tagged-source
      selection, confirmation, and partial propagation failure.

## Triage Questions

- Is capture timestamp alone a duplicate criterion, or only a prefilter for
  payload confirmation?
- Should identical full-file payloads and identical decoded pixels be separate
  match modes?
- If multiple members have tags, should TAGGER merge, choose, or ask about the
  source tags?
- Should propagation merge tags into the target or replace its existing tags?
- What scan size and progress/cancellation behavior are required?

## Validation

- Run focused duplicate-detection and tag-mutation tests.
- Run the full test suite and Ruff for modified files.
- Benchmark large-workspace scanning after the performance milestone work.
