# 01 — Prevent Incorrect Empty IPTC Filter Results During Startup Indexing

Status: needs-triage
Category: bug
Priority: high
Milestone: M3 — Metadata integrity and cache-backed IPTC workflow
Blocked by: None

## Problem

When a large folder is opened, the IPTC-empty filter can run before the folder's SQLite index has been populated. Pressing `Ctrl+E` shortly after loading `Fotos\\Themen` can therefore produce zero matches, even though the folder contains untagged photos. Later in the same application session, the same workflow reports `Match 2721 files` (or otherwise finds the expected files).

Reported example:

- File: `C:\\Users\\janwa\\Pictures\\Fotos\\Themen\\Affen\\Affen Papa\\IMG_5759.JPG`
- The file has no IPTC tags.
- Open `Fotos\\Themen` and press `Ctrl+E` immediately.
- Actual result: everything is filtered out / 0 matches.
- Later in the same session: the filter finds 2721 files.

## Goal

Ensure `Ctrl+E` never presents an index-startup race as a confirmed zero-result IPTC-empty view. The filter must eventually include existing files without requiring the user to toggle it off and on again.

## Desired Behavior

1. Reproduce the workflow with a sufficiently large fixture or a deterministic delayed index refresh.
2. If the index is not yet ready when `Ctrl+E` is pressed, either defer the filter until the relevant index update is complete or mark the result as provisional and automatically apply the corrected result when that update completes.
3. A genuinely empty IPTC-empty result must remain possible after the index is ready; do not turn every zero-result query into an unbounded scan.
4. Preserve the current workspace, selection, stale-completion, and background-thread guarantees.
5. The example `IMG_5759.JPG` must appear in the IPTC-empty view once its index state has been read.

## Investigation Notes

The current UI starts an asynchronous SQLite-backed IPTC-empty read using the current workspace paths. Folder discovery separately queues index synchronization. If the read wins that race, `load_iptc_empty_photos()` can see no indexed rows and return an empty result. The normal post-index-update refresh check appears to apply only after a completed IPTC-empty view, so verify whether an initially empty provisional view is being refreshed or silently left empty.

This is a suspected startup ordering/race mechanism, not yet a confirmed root cause. Check index initialization, discovery completion, index refresh scheduling, IPTC-empty read invalidation, and the handling of zero-result provisional views.

## Acceptance Criteria

- [ ] A deterministic regression test reproduces the early-`Ctrl+E` workflow against an incomplete index.
- [ ] The regression test fails before the fix and passes after it.
- [ ] An untagged existing file is included after startup indexing completes, without manually toggling `Ctrl+E` again.
- [ ] A truly empty ready index still displays zero matches.
- [ ] Older reads or index updates cannot replace a newer workspace/filter state.
- [ ] SQLite, filesystem, and metadata operations remain off the Qt UI thread.
- [ ] Existing IPTC-empty, indexed-search, and startup-loading tests continue to pass.

## Out of Scope

- Changing the definition of an IPTC-empty photo: canonical `IPTC:Keywords` remains authoritative.
- Changing the explicit refresh behavior for an already completed, stable IPTC-empty view.
- A general redesign of the index refresh engine.

## Comments

Created from a user report. The expected behavior and exact timing should be confirmed during triage with a large-folder reproduction or a captured startup timeline.
