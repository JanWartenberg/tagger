# 01 — Define Directory Exclusion Filter Workflow

Status: completed
Priority: medium
Category: product-discovery
Milestone: M5 — Composable workspace filtering
Blocked by: None

## Goal

Specify the smallest coherent workspace-local directory-exclusion condition for workflows such as showing untagged 2025 photos while excluding every photo under a `Werkstatt` directory.

## Recorded Decisions

- Exclusions are an insertion-ordered, normalized set of exact ancestor-directory names, matched case-insensitively on every platform. A duplicate name, including a casing or Unicode-equivalent variant, is a no-op.
- Each valid value is NFC-normalized and trimmed. Empty values and values containing `/` or `\` are rejected without changing the workspace; the draft remains focused with concise inline guidance. Names are not required to occur in the current result.
- Every subtree rooted at a matching directory is excluded, regardless of nesting depth; repeated matching directory names at different depths are all excluded. The loaded workspace root counts as an ancestor directory.
- Distinct exclusions compose as logical AND/NOT with each other and with date, indexed-search, IPTC-empty, and filename conditions. For example, `Werkstatt` and `alles` exclude either matching subtree.
- The first version uses a dedicated **Exclude folder** draft field in the Files-pane filters, not the basename-only filename filter. Enter or `:excludedir <name>` commits a value; Enter then clears the draft and retains focus for another value. Escape discards an uncommitted draft and returns focus to Files.
- Each active exclusion is visible as an ordered removable chip such as `Excluded: Werkstatt ×`. Chip removal is keyboard-focusable and activates with Enter or Space with an accessible removal label.
- `:focusexcludedir` and contextual `Alt+X` focus the draft field. `:clearexcludedir <name>` removes one normalized exclusion; `:clearfilters` removes all exclusions with the other workspace conditions.
- A valid exclusion that leaves no visible photos remains active and shows the existing “No photos match the active filters.” state with its chips visible.
- When the first exclusion is added, capture selection, active photo, and Files-pane scroll anchor. Repair selection to the first remaining visible photo when necessary. Restore captured state only when the last exclusion is removed; if a captured path no longer belongs to the current workspace, retain normal repaired selection.
- Additive dropped directories remain in the same workspace and are subject to active exclusions. Folder reload replaces the workspace and clears exclusions and their restoration state.
- Active exclusions apply to the latest completed indexed-search or IPTC-empty result only; stale background completions must not alter the current workspace.
- `PhotoWorkspace` owns normalized exclusions, derived membership, selection repair, and restoration state. `MainWindow` owns controls, chips, validation, focus, shortcuts, and rendering.

## Completion

The workflow is approved. Create a separately scoped implementation ticket; do not expand this product-discovery ticket into implementation work.

## Constraints

- Do not reinterpret the existing basename-only filename filter as a path filter.
- Do not add arbitrary negation syntax, general boolean queries, global path search, filesystem rescans, SQLite schema/query work, globbing, regular expressions, saved filters, or persisted state.
- Keep logical filter state and derived membership in `PhotoWorkspace`; keep Qt controls and rendering in `MainWindow`.

## Example

With date query `2025`, the IPTC-empty condition active, and directory exclusion `Werkstatt`, TAGGER shows only photos that satisfy all three conditions and whose path is not inside a matching `Werkstatt` directory subtree.
