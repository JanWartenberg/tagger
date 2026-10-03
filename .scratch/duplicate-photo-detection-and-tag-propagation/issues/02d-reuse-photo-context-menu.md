# 02d — Reuse the photo context menu in Duplicate review

Status: completed
Category: feature
Priority: medium
Milestone: M9 — Repeatable real-file acceptance

## Goal

Right-click a candidate image/card to get the same file context menu as the
Tagger Photo Workspace: Open, Open in GIMP, Copy file path, Reveal in Explorer,
and containing-folder exclusion where available.

## Acceptance

- [x] Both views import the same menu builder; no duplicated menu definitions.
- [x] Candidate actions target the clicked photo, independent of Workspace selection.
- [x] Existing open/GIMP/clipboard/reveal service implementation and error reporting
  are reused; Workspace multi-selection behavior remains unchanged.
- [x] Opening the menu and using file actions do not change source/target choices.
- [x] Folder exclusion reuses the tagging filter; its tooltip explains that frozen
  duplicate scan findings are unchanged.
- [x] Maintainer confirms native Windows menu/open/GIMP/clipboard behavior.

## Delivery

Shared builder: `tagger_app/ui/photo_context_menu.py`. Candidate previews and cards
request it via standard Qt context-menu events. The original file pane retains
its clicked-photo selection rules and multi-selection prompts.

Public Qt tests invoke the candidate image's context event, compare menu entries,
exercise service-boundary actions against the clicked path, verify unchanged
Workspace/review selections, and check error reporting/folder exclusion. Existing
file-pane context-menu tests remain in the suite. No real external app is launched
by automated tests.

Maintainer reported gray-on-gray Duplicate review menu text while the tagging menu
is readable. Contrast defect and fix are tracked in 02e, now explicitly accepted. On 2026-10-03, the maintainer confirmed Open, GIMP, Copy file path and Reveal
use the clicked photo, and folder exclusion affects the tagging Workspace.
Native action acceptance is complete. No additional menu implementation is planned.
