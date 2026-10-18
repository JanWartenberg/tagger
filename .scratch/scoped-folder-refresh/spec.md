# Scoped Folder Refresh

Status: completed
Priority: high

## Problem

After photos are copied into a folder on disk, TAGGER has no explicit action that refreshes both that folder's Photo Workspace and its entries in the existing index. Reopening a folder discovers files, while `:reindex` refreshes the entire active index root. With approximately 30,000 photos below `C:\Users\janwa\Pictures\Fotos`, a full-root refresh is disproportionate to a few new files in `Vögel\zu_bearbeiten`.

The reported missing DSC06827 and subsequent photos are motivation, not a confirmed diagnosis of an indexing defect. Their absence has not been reproduced against the user's database.

## Decision

Provide `F5` and `:refreshfolder` to refresh a specific folder recursively in the background. Reconcile only that subtree in the existing active-root index, then refresh the current eligible view. Preserve active filters and surviving selection. Make the target folder visible in progress feedback.

The target is the most recent explicitly chosen folder, independent of the index root and of paths in search results. If none is known, ask for a folder using the existing folder picker. Never infer the entire index root as a fallback. The detailed behavior and acceptance criteria are in [ticket 01](issues/01-refresh-folder-and-index-subtree.md).

## Scope

One implementation ticket. No filesystem watcher, full-index refresh redesign, or duplicate-candidate rescan is required.

## Implementation State

Implemented and independently reviewed in three rounds; final portable tests and real-file acceptance passed. The maintainer-executed Windows real-file acceptance also passed with independently inspected evidence; see ticket 01 for the report and limits.
