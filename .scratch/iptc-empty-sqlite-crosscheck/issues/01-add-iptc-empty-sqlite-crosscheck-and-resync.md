# 01 — Refresh an IPTC-Empty View After Background Index Update

Status: completed
Category: feature
Priority: medium
Milestone: M3 — Metadata integrity and cache-backed IPTC workflow
Blocked by: None

## Goal

Make IPTC-empty filtering immediately usable from SQLite while letting the normal background index update repair and verify that cached answer without unexpectedly changing the active view.

## Resolved Direction

- An SQLite-derived IPTC-empty result is always eligible as the immediate, provisional answer, including when the index is incomplete or stale. Regular index updates make it progressively more accurate.
- Do not start a second full file-metadata crosscheck for this filter. Reuse the active root's normal background index update started after opening a folder or by `:reindex`; it already reads file metadata and repairs SQLite.
- The completed update never changes an active IPTC-empty Photo Workspace view automatically.
- If that view was derived from an older index revision, the same root and Photo Workspace are still current, and a fresh SQLite query would change its visible membership, show a persistent non-modal footer action: `Index updated — IPTC-empty results changed. [Refresh now]`.
- `Refresh now` and `:refreshiptc` perform the same explicit action: rerun the IPTC-empty SQLite query for the current Photo Workspace and apply the result atomically. No extra scan starts. If no eligible update exists, `:refreshiptc` reports that there is nothing to refresh.
- Do not add a modal dialog or a separate keyboard shortcut. The footer button and command serve mouse and keyboard workflows without interrupting current work.
- If the view has been cleared, replaced, or belongs to another root/workspace generation when the update completes, show no refresh offer.
- Confirmed tag mutations remain intentional. They update the index through the existing path; an explicit refresh applies the then-current SQLite facts rather than altering the active view implicitly.
- The footer offer states that results changed; it does not count changed photos. A failed or cancelled update discards any prior offer; only a successful newer update can offer one.
- A refresh from a database-search source view remains restricted to the current Photo Workspace and preserves its existing atomic selection/restoration rules.
- A missing `IPTC:Keywords` field is readable empty and remains in the filter.
- An IPTC field that cannot be read or interpreted is unknown, but remains in the filter with a small `?` marker beside its file-pane entry.
- A path that no longer exists is omitted from the result and follows the normal index-removal path.
- Retry an ExifTool or batch read failure. If the file still exists after the retry but IPTC remains unreadable, include it as unknown with the `?` marker rather than silently treating it as confirmed empty.
- XMP readability does not affect this filter: readable IPTC alone decides membership.

## Established Context

- This ticket synchronizes SQLite's cached IPTC-empty facts with `IPTC:Keywords` in photo files. SQLite is not a competing tag authority.
- `IPTC:Keywords` is TAGGER's canonical tag field. [03 — Resolve IPTC/XMP Mismatches Per Photo](../../iptc-xmp-keyword-mismatch-handling/issues/03-resolve-iptc-xmp-mismatches.md) implements the approved XMP compatibility-mirror policy.
- The SQLite result must use an IPTC-specific fact; it must not derive IPTC emptiness from merged tags.
- [02 — Canonical IPTC Index Facts](../../iptc-xmp-keyword-mismatch-handling/issues/02-canonical-iptc-index-facts.md) owns the canonical-IPTC schema/data migration from merged-only rows. This ticket consumes that fact and owns the provisional SQLite view plus its explicit post-update refresh workflow.

## Readability Contract

The implementation must distinguish readable empty IPTC, unreadable IPTC for an existing file, and a path that is gone. A `?` marker means the photo is an unverified IPTC-empty candidate, not that TAGGER has confirmed it is empty. It occupies the file-pane status-marker position; a pending tag-mutation spinner takes precedence temporarily and the `?` returns when that mutation settles. Ticket 02 owns the canonical IPTC storage projection; this ticket owns this workflow treatment.

## Implementation Prerequisite

[02 — Canonical IPTC Index Facts](../../iptc-xmp-keyword-mismatch-handling/issues/02-canonical-iptc-index-facts.md) is completed; its canonical IPTC index fact is available to this workflow.

## Comments

Created from the product backlog. The existing IPTC-empty filter remains authoritative until this ticket is fully triaged.

Tracker cleanup: schema/data migration and XMP policy are explicitly outside this ticket. The former standalone crosscheck and `:resync` proposal was replaced by an explicit refresh offer after the existing background index update.

## Completion

Implemented the SQLite-backed provisional IPTC-empty view, unreadable-candidate marker, post-update refresh offer, and `:refreshiptc` command. SQLite reads remain coordinator work and refresh application stays atomic in `PhotoWorkspace`.

Validation:

- `ruff check actions.py exif_tool.py exif_ui.py indexing.py photo_workspace.py services tests`
- `QT_QPA_PLATFORM=offscreen python3 -m unittest discover -s tests -v` (176 tests)
- `git diff --check`

Manual acceptance confirmed: IPTC-empty refresh workflow tested successfully.
