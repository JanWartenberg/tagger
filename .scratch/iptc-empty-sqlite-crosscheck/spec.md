# IPTC-Empty SQLite Crosscheck and Resync

Status: needs-triage
Priority: medium

## Problem Statement

The IPTC-empty filter currently derives its result from file metadata. A fast SQLite-derived result could be shown immediately, but the index may be stale or disagree with the files.

## Desired Outcome

Show the SQLite-derived IPTC-empty Photo Workspace view immediately, then verify it through a background file-metadata scan without disrupting the visible view. When verification finds a discrepancy, repair the index and let the user explicitly apply the verified result.

## Proposed Scope

- Show the SQLite-derived IPTC-empty result immediately.
- Run a full file-metadata crosscheck in the background.
- Keep the initially displayed Photo Workspace view stable; the crosscheck must never replace it automatically.
- Repair index discrepancies and report the difference through non-modal status feedback.
- Offer `:resync` to apply an already-completed crosscheck result atomically without starting another scan.
- Treat successful tag mutations made after filter activation as intentional changes, not crosscheck discrepancies.
- Retain the SQLite-derived view and report verification failure when the crosscheck fails.

The IPTC/XMP mismatch-policy follow-on owns the schema/data migration that creates canonical IPTC index facts from existing merged-only rows. This feature consumes that fact; it owns neither XMP policy nor the migration.

## Open Triage Decisions

- Exact activation and eligibility rules for SQLite-derived IPTC-empty results, including the meaning of missing or unreadable IPTC metadata in the canonical fact.
- Crosscheck batching, progress feedback, and cancellation semantics.
- Discrepancy reporting and index-repair timing.
- `:resync` command wording and behavior when no completed crosscheck exists.

## Implementation Prerequisite

Do not implement this feature until the canonical-IPTC index-fact migration from the IPTC/XMP mismatch-policy follow-on is available. Its workflow triage may proceed independently.

## Constraints

- Keep SQLite and file-metadata work off the Qt UI thread through existing coordinator seams.
- Reuse Photo Workspace atomic view transitions and stale-result rules.
- Do not make the verification result replace a user-selected view automatically.

## Out of Scope

- Changing the IPTC-empty definition.
- Automatic application of verified results.
