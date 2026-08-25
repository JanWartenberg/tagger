# 01 — Evaluate Explicit Selection-Scoped Batch Tagging

Status: completed
Priority: medium
Category: product-discovery
Milestone: M-Future — Unscheduled opportunities
Blocked by: None

## Goal

Validate a low-surprise batch-tagging workflow for the concrete case of applying the same tags to a selected set of photos, including all photos currently shown from a loaded folder.

## Recorded Product Decisions

- At two or more selected photos, replace right-side single-photo detail with the variant-B batch overview: representative-photo stack, selected-photo count, tags shared by every selected photo, and tags present on only some selected photos.
- Do not alter the Files pane or its interaction: retain Shift+Click, Shift+Arrow, Ctrl+Space, and color-only selection presentation.
- The required add flow is unchanged: select photos, press `i`, enter one autocomplete-enabled tag, press Enter, retain selection and input focus, then enter the next tag.
- Adding the tag to every selected photo is required. Removing a tag from every selected photo is also required once a complete summary confirms the tag is shared; partially shared tags are informational and not removable as shared tags.
- The batch overview must show loading, incomplete, or failed state rather than claim a tag is shared from partial data. No confirmation modal is required for deliberate selection.

## Implementation Handoff

The bounded asynchronous metadata-summary read, latest-selection-wins behavior, batch-view rendering, and validation are scoped in [02 — Implement Selection-Scoped Batch Tagging](02-implement-selection-scoped-batch-tagging.md).
## Existing Capability

`MainWindow._apply_add_tag()` already sends an added tag to `selected_file_paths()` and reports the affected file count. Reliable tag mutations already preserve pending, partial-failure, and selected retry behavior. This ticket concerns discoverability and target clarity, not a replacement mutation system.

## Prototype

Evaluate variant B of [`prototype/multi-photo-tagging-variants.html`](../../../prototype/multi-photo-tagging-variants.html). It is an in-memory throwaway prototype of the proposed batch overview. Its Files pane must retain color-only selection, without checkboxes or new selection controls. Do not promote it to production code without a separately scoped ticket.

## Constraints

- Batch writes target only explicit Files-pane selection; "all shown" respects active Photo Workspace conditions.
- Preserve the active photo as an inspection concept, but do not show its single-photo detail while the batch overview is active.
- Preserve completed reliable-tag-mutation behavior and current background execution.
- Do not add a recursive folder operation, hidden-result selection, saved batch selections, or a separate bulk-edit mode unless concrete evidence requires it.

## Comments

Created after real use contradicted the earlier decision to defer multi-photo tagging: applying the same two tags to a deliberate selection, sometimes a whole shown folder view, is now a repeated concrete need. The earlier evaluation remains historical evidence; this ticket reassesses the workflow from new evidence rather than reopening completed work.

## Completion

Product decisions and implementation handoff are recorded above. [02 — Implement Selection-Scoped Batch Tagging](02-implement-selection-scoped-batch-tagging.md) is ready for implementation.
