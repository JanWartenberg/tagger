# 01 — Add IPTC-Empty SQLite Crosscheck and Resync

Status: needs-triage
Category: feature
Priority: medium
Milestone: M3 — Metadata integrity and cache-backed IPTC workflow
Blocked by: None

## Goal

Make IPTC-empty filtering fast from the index while preserving a trustworthy, user-controlled file-metadata verification path.

## Proposed Scope

- Render an immediate SQLite-derived IPTC-empty result.
- Schedule a background file-metadata crosscheck without changing that result automatically.
- Repair detected index discrepancies and expose normal status feedback.
- Add `:resync` to apply the completed verified result atomically.
- Preserve intentional post-activation tag mutations and failure behavior.

## Established Context

- This ticket synchronizes SQLite's cached IPTC-empty facts with `IPTC:Keywords` in photo files. SQLite is not a competing tag authority.
- `IPTC:Keywords` is TAGGER's canonical tag field. The separate IPTC/XMP mismatch-policy ticket owns how the XMP compatibility mirror is handled.
- The SQLite result must use an IPTC-specific fact; it must not derive IPTC emptiness from merged tags.
- A follow-on to the IPTC/XMP mismatch-policy ticket owns the canonical-IPTC schema/data migration from merged-only rows. This ticket consumes that fact and owns only the crosscheck, result application, cache repair, and `:resync` workflow.

## Required Triage Before Implementation

- When is an SQLite-derived IPTC-empty result eligible: only with a fully initialized/current index, or may it be shown from a stale or incomplete index?
- What exact field-specific index fact defines IPTC-empty, including missing or unreadable metadata? The IPTC/XMP mismatch-policy follow-on owns migration of existing merged-only rows to that fact.
- Is verification always a full active-root scan, or is it limited to a defined source or candidate set?
- What batching, progress cadence, persistent feedback, and cancellation behavior does verification have?
- Which differences count as discrepancies: changed IPTC emptiness, missing/deleted files, newly discovered files, unreadable files, or all of them?
- When are index repairs committed, and how are their effects reported without changing the initially displayed Photo Workspace view?
- How do tag mutations after filter activation remain intentional rather than discrepancies while their confirmed metadata still wins in the repaired index?
- What makes a completed verification eligible for `:resync`—the same root, workspace generation, and filter activation—and what happens when no eligible completed verification exists or it failed?
- How do folder changes, a newer filter activation, database search, or another superseding Photo Workspace transition affect verification completion and `:resync` availability?

## Implementation Prerequisite

Do not implement this ticket until the canonical-IPTC index-fact migration owned by the IPTC/XMP mismatch-policy follow-on is available. This does not block completing this ticket's workflow triage.

## Comments

Created from the product backlog. The existing IPTC-empty filter remains authoritative until this ticket is fully triaged.

Tracker cleanup: schema/data migration and XMP policy are explicitly outside this ticket; its remaining triage is limited to the SQLite-backed verification and explicit-result-application workflow.
