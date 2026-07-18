# Reliable Tag Mutations

Status: completed
Priority: high

## Problem Statement

TAGGER updates cached metadata and the visible UI before ExifTool confirms a write. A failed or partially failed queued mutation can leave the Photo Workspace presenting tags that were not persisted to the photo files.

## Solution

Make queued tag mutations explicitly reliable: preserve responsive feedback while distinguishing pending from confirmed metadata and recovering the UI, cache, index, and IPTC-empty visibility after failure.

## User Stories

1. As a TAGGER user, I want a failed tag write to be clearly reported, so I do not trust metadata that was not saved.
2. As a TAGGER user, I want the displayed tags to return to confirmed file state after a failed write.
3. As a TAGGER user, I want later queued edits to have deterministic behavior after an earlier edit fails.
4. As a TAGGER user, I want multi-photo writes to report which photos succeeded or failed.
5. As a maintainer, I want tag, cache, index, and IPTC-empty filter updates to share one confirmed result.

## Implementation Decisions

- Retain background execution and ordered mutation processing.
- Model pending and confirmed metadata distinctly enough that failure cannot silently become displayed truth.
- Display a non-blocking pending indicator (for example, a spinner/hourglass) while a tag mutation has been submitted but is not yet confirmed; users may continue preparing further work.
- Show a persistent mini-indicator for pending and failed mutations on each affected entry in the photo-files pane, and explain the state in the selected photo's detail area.
- Provide a `:retry` keyboard command in addition to the visible retry affordance; it retries only failed mutations for currently selected photos.
- Provide `:retryall` to retry all failed mutations belonging to the current Photo Workspace; it never resubmits pending mutations.
- On write failure, restore the last confirmed metadata state, show a visible failed state, and offer retry; do not leave failed requested tags presented as file truth.
- For a partial multi-photo failure, retain confirmed changes for successful photos and restore, mark, and retry only failed photos; show a summary of both outcomes.
- Preserve later pending mutations for a photo when an earlier mutation fails; recompute their requested state from the last confirmed metadata rather than discarding the user's later input.
- Before executing a pending mutation or retry, reread the current file metadata and reapply the original user intent so unrelated external metadata changes are preserved.
- When a photo leaves the Photo Workspace, discard its queued mutations. Let already in-flight writes finish for file/index correctness, but never let their completion alter the new Photo Workspace view.
- Define the result contract for complete success, complete failure, and partial success before applying UI or index changes.
- Make the index reflect only confirmed persisted metadata.
- Keep Photo Workspace responsible for IPTC-empty filter-view lifecycle: confirmed mutations do not revise an active filter view; an explicit user refilter computes a new view from current file metadata.

## Testing Decisions

- Test mutation coordination with a fake metadata writer that succeeds, fails, and partially fails.
- Assert observable cache/UI/index/filter outcomes rather than queue internals, including per-photo outcomes for a partial multi-photo failure and an earlier failed mutation followed by a later pending mutation on the same photo.
- Cover an external metadata change before execution or retry; unrelated externally added tags must remain after the user's intent is replayed.
- Cover a Photo Workspace change with both queued and in-flight mutations: queued work for departed photos is discarded, while in-flight completion does not render into the replacement workspace.
- Keep direct tag transformation tests independent from Qt and ExifTool.
- Add offscreen adapter coverage for list/detail pending and failed indicators, `:retry` scoped to selected photos, and `:retryall` scoped to failed mutations of the current Photo Workspace.

## Out of Scope

- New tagging workflows, tag suggestions, or changes to IPTC/XMP formats.

## Further Notes

All identified product decisions are resolved: show requested tags immediately as a visibly pending tag mutation without blocking further work; on failure, restore confirmed metadata and offer retry; for partial batches, retry only failed photos; retain later pending mutations after an earlier failure; reread and replay intent to preserve unrelated external changes; show per-photo indicators in the photo-files pane and explain state in the detail area; `:retry` retries failed mutations for selected photos; `:retryall` retries all failed mutations of the current Photo Workspace; discard queued work when its photo leaves the Photo Workspace and prevent in-flight completion from rendering into a replacement workspace.

## Comments

> *This was generated by AI during triage.*

## Agent Brief

**Category:** bug
**Summary:** Make visible tag edits reliable while preserving TAGGER's non-blocking keyboard workflow.

**Current behavior:** TAGGER renders optimistic tag changes before ExifTool confirms them. A failed queued write reports an error but can leave cache, index, filter visibility, and the photo-files pane representing unpersisted metadata.

**Desired behavior:** Requested tag changes appear immediately as pending and remain visibly distinct from confirmed file metadata. Users may continue selecting photos and preparing mutations. Successful writes become confirmed; failed writes restore confirmed metadata, remain visibly failed, and can be retried without losing later user input or unrelated external file changes.

**Key interfaces:**
- The tag-mutation result contract must express confirmed, failed, and partial per-photo outcomes.
- The mutation coordinator must retain confirmed state and ordered pending mutation sequences per photo.
- The Photo Workspace adapter must render per-photo pending/failed indicators and detail-state explanations without owning mutation truth.
- Command routing must provide `:retry` for failed mutations of selected photos and `:retryall` for all failed mutations of the current Photo Workspace.

**Acceptance criteria:**
- [ ] A submitted mutation is non-blocking and visibly pending in the affected photo-files-pane entries and selected-photo detail area.
- [ ] A successful mutation becomes confirmed only after a successful write; the index and IPTC-empty visibility reflect confirmed state.
- [ ] A failed mutation restores confirmed metadata, visibly reports failure, and is retryable.
- [ ] In a partial multi-photo outcome, successful photos remain confirmed and only failed photos are restored and retried.
- [ ] A later mutation for a photo survives an earlier failure and is recomputed from confirmed metadata.
- [ ] Execution and retry reread file metadata and preserve unrelated external changes when replaying user intent.
- [ ] `:retry` is limited to failed mutations for selected photos; `:retryall` is limited to failed mutations in the current Photo Workspace.
- [ ] Reloading or replacing the Photo Workspace discards queued work for departed photos and prevents in-flight completion from updating the replacement view.
- [ ] Pure coordinator tests and offscreen adapter tests cover the specified observable behaviors.

**Out of scope:**
- New tagging workflows, suggestions, or metadata-format changes.
- Cancelling an ExifTool write that has already been sent.
