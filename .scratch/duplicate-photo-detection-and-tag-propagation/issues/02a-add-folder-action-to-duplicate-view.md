# 02a — Add Folder Action to Duplicate Review

Status: completed
Category: feature
Priority: medium
Milestone: M8 — Duplicate candidate review and tag propagation
Blocked by: None

## Goal

Make the existing Add folder function available from the duplicate-review view so
a user does not need to return to the tagging workspace to add a photo folder.

## Scope

- Add a visible Add folder option or button to duplicate review.
- Reuse the existing folder-selection and Photo Workspace loading behavior rather
  than introducing a separate discovery path.
- Use the exact folder selected from Duplicate Review as its subfolder scan scope
  and automatically collect its paths so the scan size is visible, while keeping
  detector execution explicit.
- Keep the user in duplicate review after choosing a folder.
- Preserve the existing background discovery, index, error, and cancellation
  behavior.

## Acceptance Criteria

- [x] Duplicate review exposes an Add folder action.
- [x] Choosing it uses the same folder dialog and loading behavior as Add folder
      in the tagging workspace.
- [x] Adding a folder automatically calculates the selected subfolder's scan size
      without widening it to the parent index root or starting a detector scan.
- [x] The duplicate-review view remains active while the folder loads and after
      loading completes.
- [x] Cancelling the folder dialog leaves the current workspace and duplicate
      review state unchanged.
- [x] Tests cover successful selection, dialog cancellation, view preservation,
      and absence of implicit scan work.

## Implementation Progress

- Duplicate review exposes the shared Add folder flow in its header.
- The last-opened-folder behavior remains provided by the existing folder dialog.
- Successful loading updates the index, freezes the exact selected folder as a
  subfolder scope, calculates its scan size, and leaves detector execution behind
  the explicit Start scan action.
- The view remains active and does not move focus into the hidden tagging view.
- Accepted by the maintainer; ticket 02 is already accepted.

## Next-session Acceptance Review

Confirm that:

1. Add folder is visible in Duplicate Review.
2. It reuses Tagging's folder picker and workspace-loading behavior.
3. The exact selected folder becomes the duplicate subfolder scope rather than
   widening to the parent index root.
4. Scope collection is automatic, but duplicate detection remains explicit.
5. Duplicate Review stays open during and after folder loading.
6. Cancelling the picker leaves the workspace and review state unchanged.
7. Existing background discovery, indexing, error, cancellation, and stale-result
   protections remain intact.
8. Automated coverage verifies successful loading, cancellation, view
   preservation, exact scope, and no implicit detector scan.

## Out of Scope

- Automatically starting duplicate-candidate detection after loading.
- Changing Add folder semantics in the tagging workspace.
- Tag propagation.
