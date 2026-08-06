# 03 — Preserve the Index Root After an Empty Database Search

Status: completed
Category: bug
Priority: medium
Milestone: M3 — Metadata integrity and cache-backed IPTC workflow
Blocked by: None

## Goal

A database search that returns no photos must retain its originating index root so that the next query searches the same index.

## Scope

- Keep the active index root when the Photo Workspace is empty because of a database-search result.
- Do not fall back to `DEFAULT_INDEX_ROOT` for a follow-up query in that state.
- Preserve normal default-root selection when photo paths are available.

## Acceptance Criteria

- After an empty `:search`, a subsequent query is sent to the same index root.
- A later matching query can populate the empty database-search view without requiring `:clearsearch`.
- A regression test uses an existing but distinct default root to prove it cannot replace the active root.

## Validation

- Focused Qt offscreen regression test passed.
- Manual validation: an XMP-only empty query followed by an IPTC-only query retained the temporary-folder index root and returned the IPTC match.
