# 01 — Define Directory Exclusion Filter Workflow

Status: needs-triage
Priority: medium
Category: product-discovery
Milestone: M5 — Composable workspace filtering
Blocked by: None

## Goal

Specify the smallest coherent workspace-local directory-exclusion condition for workflows such as showing untagged 2025 photos while excluding every photo under a `Werkstatt` directory.

## Required Triage Before Implementation

- Establish precise normalized directory/subtree matching semantics, including repeated directory names at different depths and platform path behavior.
- Decide the dedicated UI and command interaction, plus the active-filter indicator and clear behavior.
- Define composition with date, indexed-search, IPTC-empty, and filename conditions as an explicit logical AND with the directory exclusion predicate.
- Define selection, active-photo, empty-state, restoration, discovery, and drag/drop behavior when the condition changes.
- Confirm the smallest `PhotoWorkspace` seam and create a separately scoped implementation ticket only after the workflow is approved.

## Constraints

- Do not reinterpret the existing basename-only filename filter as a path filter.
- Do not add arbitrary negation syntax, general boolean queries, global path search, filesystem rescans, SQLite schema/query work, globbing, regular expressions, saved filters, or persisted state.
- Keep logical filter state and derived membership in `PhotoWorkspace`; keep Qt controls and rendering in `MainWindow`.

## Example

With date query `2025`, the IPTC-empty condition active, and directory exclusion `Werkstatt`, TAGGER shows only photos that satisfy all three conditions and whose path is not inside a matching `Werkstatt` directory subtree.
