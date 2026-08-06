# 03 — Resolve IPTC/XMP Keyword Mismatches Per Photo

Status: ready-for-agent
Category: enhancement
Priority: high
Milestone: M3 — Metadata integrity and cache-backed IPTC workflow
Blocked by: 02

## Goal

Replace merge-and-sync mismatch handling with the approved per-photo Resolve workflow while retaining pending, failed, and retryable tag-mutation behavior.

## Module and Interface

Introduce one reconciliation module behind a small interface that accepts the two keyword-field states and returns either no discrepancy or the field-specific Resolve choices. It uses ticket 02's canonical-keyword normalization and owns comparison and the S1–S8 classification from the approved policy. `MainWindow` remains its Qt adapter; it must not duplicate comparison or resolution rules.

`ExifTool` receives one field-specific write interface that writes chosen IPTC and XMP values in one operation. The tag-mutation coordinator remains the seam for the operation lifecycle and its confirmed, pending, failed, and workspace-generation facts.

## Scope

- Detect discrepancies when the active photo is selected; do not scan in discovery, indexing, or IPTC-empty filtering.
- Normalize and compare fields exactly as policy issue 01 specifies: trim outer whitespace, ignore empties, deduplicate in place, compare case-insensitively and after Unicode NFC normalization, and treat keyword hierarchy syntax as literal text.
- Render IPTC values as the current tags. S3 (non-empty IPTC and empty XMP) is silent and leaves XMP empty during later ordinary tag mutations.
- For S2 and S5–S8, present one modal for the active photo with per-tag and whole-list copy controls, per-tag and whole-list deletion, Apply, and Cancel. The dialog may leave fields mismatched.
- For an unreadable field, show readable values but permit only deleting the unreadable field or cancelling; never offer a derived overwrite.
- Reread both fields immediately before Apply when possible. If that reread fails, apply the selection-time choices without additional synchronization/conflict behavior.
- Route one Apply through the tag-mutation coordinator, write both chosen fields in one ExifTool operation, make at most three total attempts, and expose terminal failure through the existing footer/session-error conventions.
- Replace the current multi-selection `Resolve (sync both)` action with this single-photo workflow. Update the action catalogue, README, and characterization tests to match the delivered behavior.

## Acceptance Criteria

- S1, S3, and S4 show no mismatch workflow; S2 and S5–S8 offer the Resolve modal; unreadable fields offer only the recovery path above.
- The tag pane never displays XMP-only values as current tags.
- Copy, deletion, Cancel, Apply, failed write, retry, and a Photo Workspace transition retain the coordinator's established confirmed/pending/failed guarantees.
- Apply issues one field-specific ExifTool operation; it does not merge-and-sync implicitly.
- The index receives confirmed canonical-IPTC state only, through ticket 02's projection.
- Focused reconciliation, ExifTool, coordinator, and offscreen MainWindow tests cover the state matrix and retry limit.

## Out of Scope

- Background mismatch discovery.
- Multi-photo Resolve.
- SQLite IPTC-empty crosscheck verification and `:resync`.

## Validation

- Run focused reconciliation, mutation-coordinator, indexing, and MainWindow tests, then the full test suite.
- Run the Windows offscreen acceptance suite before completion.
