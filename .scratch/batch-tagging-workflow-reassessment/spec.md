# Batch Tagging Workflow Reassessment

Status: ready-for-agent
Priority: medium

## Problem Statement

The earlier multi-photo tagging evaluation concluded that copy/paste was sufficient for repeated tagging. Subsequent real use has identified concrete cases where a user wants to apply the same two tags to a deliberate selection, sometimes every shown photo in a loaded folder.

TAGGER already applies an added tag to all selected Photo Workspace photos and retains reliable per-photo pending, failure, and retry behavior. The remaining question is whether that existing capability is sufficiently discoverable and unambiguous for deliberate batch work.

## Desired Outcome

Make the smallest evidence-backed change that lets a user confidently select the intended visible photos and add successive tags to that same selection, without changing the Files pane or reliable tag-mutation semantics.

## Proposed Low-Surprise Direction

- Retain the current Files-pane selection as the sole batch target. Do not change that pane or its interaction: no checkboxes, selection tray, count control, new selection gesture, or changed selection semantics. Existing Shift+Click, Shift+Arrow, and Ctrl+Space behavior and color-based selection presentation remain unchanged.
- When multiple photos are selected, replace the right-side single-photo detail with a batch overview (prototype variant B): a small stack of representative photos, the selected-photo count, tags shared by every selected photo, and tags present on only some selected photos.
- Put the existing add-tag action in that overview. Let the user add the first tag, then the second, while preserving the selection. Existing queued/confirmed/partial-failure feedback continues to state the affected file count.
- Do not add a confirmation modal for ordinary deliberate selection. The batch overview and existing immediate queued-result feedback are the safety mechanism; reassess only if real use shows accidental broad writes.
- For "the whole folder", the user uses the existing Files-pane selection behavior after loading the folder and clearing any conditions they do not intend to constrain. Do not add a separate recursive directory-target operation.

## Recorded Decisions

- Show the batch overview exactly when two or more photos are selected; return to the existing single-photo detail for zero or one selected photo.
- Adding tags to every selected photo is the required first capability. The existing flow remains: select photos, press `i`, enter one tag with existing autocomplete, press Enter, retain selection and input focus, then enter the next tag.
- Also allow removing a tag from every selected photo, but only after a complete summary confirms that the tag is present on every target. This makes an accidental add reversible without presenting a partial removal as a shared-tag action.
- Show tags present on only some selected photos as information, not as removable shared tags.
- A batch overview must show a loading state until its tag summary is complete. It must state incomplete or failed reads rather than infer shared tags from partial data.
- Keep the existing no-modal approach; target selection plus overview and mutation feedback are sufficient acknowledgement.

## Remaining Engineering Questions

- The current cache is populated primarily for the active photo. Determine the bounded asynchronous batch-read path for uncached selected photos, including progress, errors, cancellation, and latest-selection-wins delivery; never read all selected metadata on the Qt UI thread.
- Define the exact rendering and focus restoration when selection changes or the Photo Workspace is replaced while a batch summary is loading.
- Validate the summary and mutation flow with real small selections, whole-folder selections, and filtered views.

## Constraints

- Preserve the Photo Workspace as the owner of membership, selection, and active photo. `MainWindow` owns the batch-overview presentation.
- Preserve canonical `IPTC:Keywords`, asynchronous reliable mutations, per-photo pending/failed indicators, partial-batch outcomes, and `:retry` semantics. A shared-tag removal is enabled only after a complete summary.
- A batch target is always an explicit selection. It must not silently mean the loaded folder, a recursive filesystem subtree, all search results, or photos hidden by active conditions.
- Do not add a second durable batch-selection model, a new metadata format, synchronous file writes, filesystem rescans, saved selections, or a general bulk-edit workflow.

## Implementation

Implementation is ready in [02 — Implement Selection-Scoped Batch Tagging](issues/02-implement-selection-scoped-batch-tagging.md). It defines the asynchronous canonical-IPTC summary seam, stale-result rules, and validation scope.

## Prototype

Variant B in [`prototype/multi-photo-tagging-variants.html`](../../prototype/multi-photo-tagging-variants.html) illustrates the selected direction: it replaces single-photo detail with a compact batch overview while keeping the Files pane's color-based selection presentation unchanged. Variants A, C, and D are not the proposed direction.
