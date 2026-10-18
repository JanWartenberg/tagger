# 01 — Refresh a Folder and Its Index Subtree

Status: completed
Category: feature
Priority: high
Blocked by: None

## Goal

Discover externally added, changed, and removed photos in a chosen folder without refreshing unrelated folders below a large index root. Update the Photo Workspace or current indexed-search results after the scoped index reconciliation.

## Resolved Product Behavior

- Register `F5` and `:refreshfolder` through the action catalogue for the tagging view. Use the concise English label `Refresh folder` and document the action.
- Refresh the last explicitly selected folder, including its descendants, matching existing folder-load recursion. Retain that target when switching to indexed search. Dropped folders and individual search-result paths do not silently replace it. If no target is known, show a folder picker; cancellation does nothing. A folder chosen there becomes the refresh target without first replacing an active search.
- Show the target path in non-modal progress feedback. If the chosen folder is the active index root itself, refreshing its whole subtree is intentional; do not substitute the root for an unknown target.
- Use the existing active index root and database when the target is inside it. An existing nested `.tagger` directory does not redirect this operation to another database. Do not change the configured index root. Outside the active index root, refresh the folder view only and clearly indicate that no index update occurred; do not create or switch databases implicitly.
- Add newly discovered supported photos, update indexed metadata for new or changed files, and remove missing index entries only within the target subtree. Treat moves as independent removal and discovery. Match path boundaries correctly, including Windows case/path normalization; similarly prefixed siblings are outside the scope.
- For an ordinary folder Photo Workspace, replace its folder membership with the successfully discovered current set and reapply existing filename and directory-exclusion filters. Preserve the active photo and selected surviving paths; if the active photo disappeared, use the existing deterministic selection fallback.
- For a current indexed search, reconcile the subtree and then rerun the same query against the active-root database. Preserve its active filters and surviving selection. This query may return matches anywhere in that index; filesystem discovery and metadata reconciliation remain restricted to the chosen subtree.
- Respect the established stable IPTC-empty result behavior: do not silently recompute membership. Reuse the explicit refresh offer after an index update, and exclude removed files from the view. New photos enter that filtered result only when the user explicitly reapplies the filter.
- For a mixed Photo Workspace created by dropped files/folders, reconcile membership only inside the target subtree and retain unrelated workspace photos. Do not refresh duplicate-candidate results as part of this action.

## Execution and Failure Semantics

- Keep discovery, metadata reads, SQLite operations, and potentially large view preparation off the UI thread using existing coordinator seams. Selection, preview, and tagging remain responsive.
- Serialize index reconciliation through the existing per-root queue and preserve confirmed metadata writes. Repeated refresh requests for the same pending/running target and workspace generation are deduplicated; an explicit refresh from a newer view queues a successor. Do not overlap a root refresh or metadata write outside the queue.
- Apply results only while the originating view, query, root, and workspace generation remain eligible. An obsolete completion must not restore an older view or replace unrelated status feedback. Already queued index work may finish for index consistency.
- Do not reset the workspace to an empty list at refresh start. Retain the usable view until a successful replacement can be applied.
- Report inaccessible folders, metadata failures, and index failures visibly without claiming success. A missing/inaccessible target or incomplete enumeration must not be interpreted as an empty subtree and trigger bulk deletion. Preserve existing records for unreadable files rather than treating them as missing. No fallback full-root scan is allowed.
- A scoped refresh must not mark the entire index root fresh or invalidate unrelated full-refresh recovery state. Full-root freshness and checkpoints retain their existing meaning.

## Acceptance Criteria

Checked items have portable automated coverage. Windows real-file acceptance, including native junctions, sharing locks and process cleanup, also passed; see the inspected report below.

- [x] After loading a folder, externally copy a supported JPEG into it; F5 adds it to the ordinary folder view and the existing active-root index without reopening the folder.
- [x] With a date search active, add a matching photo inside the refresh target; F5 updates the index and reruns the query so the new match appears. Use real EXIF capture dates in accordance with `docs/adr/0001-capture-date-query-semantics.md`.
- [x] Add a file in a descendant folder, modify another file's metadata, and remove a third file; recursive refresh reconciles all three cases within scope.
- [x] Probes verify that discovery and metadata reads do not traverse unrelated sibling folders, even when they contain new files. Their index entries are unchanged, including similarly prefixed sibling paths.
- [x] A nested `.tagger` folder does not change the chosen active database. Refresh does not alter root freshness timestamps or unrelated full-refresh checkpoints.
- [x] Surviving selection, active photo, filename/directory filters, explicit IPTC-empty refresh semantics, and unrelated mixed-workspace photos follow the rules above.
- [x] No known folder opens the picker; cancelling it leaves state unchanged. An out-of-root selection performs only a folder-view refresh with accurate feedback.
- [x] Repeated requests, concurrent confirmed tag writes, a running full refresh, and switching folder/query while work is pending cannot produce overlapping writes or stale UI application.
- [x] An inaccessible target, partial enumeration failure, and unreadable photo produce accurate failure feedback without deleting valid cached records or wiping the current view.
- [x] F5 and the command use the same action; progress includes the target path and completion/failure remains non-modal. Documentation and shortcut help reflect the action.

## Implementation Pointers

- `tagger_app/ui/actions.py`: action catalogue and shortcut registration.
- `tagger_app/ui/main_window.py`: folder target tracking, active search identity, view application, filter refresh offers, progress feedback.
- `tagger_app/services/background_coordinator.py`: discovery scheduling, root serialization, request identity and stale-completion protection.
- `tagger_app/services/photo_discovery.py`: supported-file discovery, currently recursive.
- `tagger_app/indexing.py`: scoped metadata reconciliation and deletion boundaries. Reuse suitable existing seams rather than launching `:reindex`.
- `tagger_app/photo_workspace.py`: membership, filters, and selection reconciliation.

## Verification and Handoff

Add focused index/coordinator/offscreen UI tests for the criteria above. Extend the real-file suite with disposable JPEGs and real ExifTool to verify external addition, changed capture metadata, removal, preserved sibling entries, and search reapplication through public Qt interactions. Read `tests/acceptance/README.md` first.

Run `ruff check .`, Ruff formatting checks for modified Python files, `QT_QPA_PLATFORM=offscreen pytest`, and `python tests/acceptance/run.py` in the development environment. Record inspected results and any unavailable Windows-only checks in this ticket and `tests/acceptance/REVIEW.md`; update `VISUAL_SMOKE.md` for the new shortcut and progress presentation. Do not require a personal-photo dataset or maintainer-run checks available to the agent.

## Comments

Implementation is complete; the maintainer explicitly requested its commit on 2026-10-18. The original missing-photo report remains unconfirmed against the maintainer's database. The required native Windows real-file acceptance has passed and its report was independently inspected. The ticket is completed; native appearance and a full Windows pytest run are not claimed.

### Independent Review

- Round 1 (two read-only reviewers): fixed cross-generation deduplication and ordinary linked-JPEG discovery after failing regression tests. Added explicit `NoUpdate` current-item flags and large/small multiselection tests for the reported selection risk; the end-to-end large-view test also passed before hardening.
- Round 2 (two fresh read-only reviewers): reproduced and fixed pending IPTC-empty filtering being stranded by a generation change, and physical-subtree escape through redirected directories. Added resolved-directory containment, a visited-directory guard and a final file containment check. Portable simulated junction tests cover sibling escape and ancestor cycles; the Windows acceptance report below additionally validates native junctions.
- Follow-up coverage also verifies filters waiting for a full-index dependency across a scoped refresh, including dependency failure. Round 3 used two fresh independent read-only reviewers; both returned no findings. No confirmed review findings remain.

### Verification and Acceptance

- Pre-scroll integration `QT_QPA_PLATFORM=offscreen python -m pytest -q`: 421 passed, 4 Windows-only skips, 33 subtests passed. Final `python tests/acceptance/run.py`: passed; independently inspected `tests/acceptance/reports/20261018T152828.979803Z/report.json`, sixteen phases / 44 passed cases (plus four diagnostic records), both backup settings. Harness hashes matched the files at that inspection, worker cleanup is verified and disposable workspaces were removed. See `tests/acceptance/REVIEW.md` for details.
- The real-file matrix now includes folder refresh under both backup settings and now requires eighteen phases / 48 cases on Linux and twenty phases / 52 cases plus native cleanup on Windows, including the separately committed scroll phases.
- `ruff check .` passed. Whole-file Ruff format check reports only two existing duplicate-context-menu lambda blocks in `main_window.py`, independently reproduced on HEAD; those unrelated lines are unchanged. New and modified sections are formatted.
- Windows acceptance: maintainer-executed run, independently inspected `tests/acceptance/reports/20261018T180842.568212Z/report.json`: Windows 11 / Python 3.14.7 / ExifTool 13.59, 20 phases / 52 passed cases in the combined working tree. Both backup modes, native junctions, sharing-lock failure/retry and five native cleanup probes passed. All phase exits are zero, child cleanup is verified and disposable workspaces were removed. Harness hashes matched current files before the post-run output-capture correction below. Native appearance and a full Windows pytest run remain unrun; no new subjective acceptance is required. Previously accepted unrelated visual checks remain accepted.
- Post-run harness correction: `mklink /J` output is now captured as bytes instead of locale-decoded text. The inspected run contained subprocess-reader `UnicodeDecodeError` tracebacks for this diagnostic output; its junction commands and feature assertions nevertheless passed. Only this capture argument changed after the inspected report. A portable subprocess probe verifies capture of byte `0x81`, Ruff passed, and the Windows branch has not been rerun after this diagnostic-only correction. No application behavior or acceptance assertions changed.
- The maintainer authorized this folder-refresh commit on 2026-10-18. Implementation, tests, completed ticket/spec and inspected acceptance evidence are included together. No merge or push requested.

### Commit Verification

The combined working tree after the separately committed scroll fix passed `ruff check .`, `QT_QPA_PLATFORM=offscreen python -m pytest -q` (424 passed, 4 Windows-only skips, 33 subtests), and `git diff --cached --check`. Ten modified/new Python files pass the Ruff formatting check; the two documented baseline lambda-format issues in `main_window.py` remain untouched. The inspected combined Windows report above remains the native functional evidence; the post-report diagnostic-only binary-capture correction has portable probe coverage. No further application code changed after the final independent reviews.
