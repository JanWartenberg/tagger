# Duplicate Photo Detection and Tag Propagation

Status: ready-for-agent
Priority: medium

## Goal

Add a separate workspace feature that scans the files currently added to the
Photo Workspace for duplicate photos, identifies whether any duplicate already
has tags, and offers to copy those tags to the other duplicates.

This feature is intentionally scheduled after the performance profiling and
fixing work.

## Scope

- Scan only the photos currently added to the Photo Workspace.
- Detect duplicate candidates using capture date/time and/or identical picture
  payload data.
- Report duplicate groups rather than silently modifying files.
- Show which photos in each group have tags.
- Let the user explicitly choose to copy tags from a tagged duplicate to the
  other photos in that group.
- Route writes through the existing tag-mutation workflow and preserve the
  canonical IPTC keyword rules.

## Decisions Required Before Implementation

- Whether matching capture date/time alone is sufficient for a duplicate, or
  only a candidate that must be confirmed by payload data.
- Which payload identity is used (full-file hash, decoded pixel hash, or another
  stable representation), including treatment of edited/resized photos.
- How missing or conflicting capture timestamps are handled.
- How multiple tagged photos in one group are reconciled.
- Whether tags are merged or replaced, and how conflicts are presented.
- How scanning progress, cancellation, stale workspace changes, and large
  workspaces are handled.

## Constraints

- Keep scanning and hashing off the Qt UI thread.
- Do not alter files until the user explicitly confirms propagation.
- Preserve existing metadata failure, retry, backup, and session-error behavior.
- Do not scan photos outside the current Photo Workspace.
