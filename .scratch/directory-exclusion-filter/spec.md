# Directory Exclusion Filter

Status: needs-triage
Priority: medium

## Problem Statement

A user can combine a capture-date query with the IPTC-empty condition, but cannot remove an unwanted directory subtree from that result. For example, while reviewing untagged photos from 2025, they need to hide photos stored in a `Werkstatt` directory.

## Desired Outcome

Allow a user to express a workspace result such as: “show all untagged photos from 2025 that are not in a Werkstatt directory,” while preserving the current Photo Workspace and composition of date, indexed-search, IPTC-empty, and filename conditions.

## Open Triage Decisions

- Define the directory matching unit: an exact normalized ancestor-directory name, a relative directory path, or another bounded form. Do not silently treat arbitrary filename text as a directory exclusion.
- Define whether an excluded directory removes its full descendant subtree and how case, Unicode normalization, Windows path separators, and duplicate directory names at different depths behave.
- Select one discoverable surface and command vocabulary without creating a general boolean-query language or overloading the filename filter’s basename-only contract.
- Specify active-condition presentation, individual clearing, empty-result behavior, focus/keyboard interaction, selection repair, and restoration.
- Confirm the ownership seam in `PhotoWorkspace` so this is an independent, workspace-local AND/NOT condition rather than parallel filtering in `MainWindow`.

## Constraints

- Keep all filter conditions workspace-local; do not add photos outside the current Photo Workspace or introduce a global path search.
- Preserve filename filtering as basename-only. Directory exclusion must have its own explicit semantics.
- Preserve date, indexed-search, IPTC-empty, filename-filter, selection, scroll-restoration, and stale-background-result behavior.
- Do not introduce general boolean expressions, arbitrary NOT syntax in indexed search, SQLite schema/query changes, filesystem rescans, globbing, regular expressions, saved filters, or persisted filter state.
- Run no potentially long filesystem or SQLite work on the Qt UI thread.
