# Refresh IPTC-Empty View After Background Index Update

Status: ready-for-agent
Priority: medium

## Problem Statement

The IPTC-empty filter currently derives its result from file metadata. SQLite can provide an immediate answer, but that cached answer can be stale while the normal background index update catches up.

## Desired Outcome

Show the SQLite-derived IPTC-empty Photo Workspace view immediately, including from an incomplete or stale index. Reuse the normal background index update to repair SQLite; do not start a second verification scan. If that update changes the answer for the still-current view, offer an explicit, non-modal refresh rather than changing the view automatically.

## Resolved Scope

- Show the SQLite-derived IPTC-empty result immediately, regardless of index freshness.
- Reuse the normal active-root background index update after folder opening or `:reindex`; it is the file-metadata verification and repair path.
- Keep an initially displayed IPTC-empty Photo Workspace view stable when the index update completes.
- Only when the same root/workspace and provisional filter view remain current and a new SQLite query has different membership, show a persistent footer action: `Index updated — IPTC-empty results changed. [Refresh now]`.
- `Refresh now` and `:refreshiptc` rerun the SQLite query for the current Photo Workspace and apply it atomically. They do not start another scan. Without an eligible completed update, `:refreshiptc` reports that there is nothing to refresh.
- Do not use a modal popup or separate shortcut.
- Treat successful tag mutations made after filter activation as intentional changes. Existing index writes record them, but the active view changes only after the user explicitly refreshes.
- The footer offer says only that results changed; it does not count changed photos.
- A cleared/replaced view, root change, workspace replacement, failed update, or cancelled update discards any refresh offer. Only a successful newer update can offer one.
- A refresh from a database-search source view remains restricted to the current Photo Workspace and preserves its existing atomic selection/restoration rules.
- A missing `IPTC:Keywords` field is a readable empty value and remains in the filter.
- An IPTC field that cannot be read or interpreted is unknown, but remains in the filter with a small `?` marker beside its file-pane entry.
- A path that no longer exists is omitted from the result and follows the normal index-removal path.
- Retry an ExifTool or batch read failure. If the file still exists after the retry but IPTC remains unreadable, include it as unknown with the `?` marker rather than silently treating it as a confirmed empty value.
- XMP readability does not affect this filter: readable IPTC alone decides membership.

[02 — Canonical IPTC Index Facts](../iptc-xmp-keyword-mismatch-handling/issues/02-canonical-iptc-index-facts.md) owns the schema/data migration that creates canonical IPTC index facts from existing merged-only rows. This feature consumes that fact; it owns neither XMP policy nor the migration.

## Readability Contract

The index/update seam must distinguish readable empty IPTC, unreadable IPTC for an existing file, and a path that is gone. A `?` marker means the photo is included as an unverified IPTC-empty candidate, not that TAGGER has confirmed it is empty. It occupies the file-pane status-marker position; a pending tag-mutation spinner takes precedence temporarily and the `?` returns when that mutation settles.

## Implementation Prerequisite

[02 — Canonical IPTC Index Facts](../iptc-xmp-keyword-mismatch-handling/issues/02-canonical-iptc-index-facts.md) is completed; this feature consumes its canonical IPTC fact.

## Constraints

- Keep SQLite and file-metadata work off the Qt UI thread through existing coordinator seams.
- Reuse Photo Workspace atomic view transitions and stale-result rules.
- Do not make a completed index update replace a user-selected view automatically.

## Out of Scope

- Changing the IPTC-empty definition for readable files.
- Automatic application of verified results.
