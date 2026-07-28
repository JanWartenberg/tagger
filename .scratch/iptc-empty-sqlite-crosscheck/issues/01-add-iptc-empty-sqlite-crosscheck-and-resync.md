# 01 — Add IPTC-Empty SQLite Crosscheck and Resync

Status: needs-triage
Category: feature
Priority: medium
Blocked by: None

## Goal

Make IPTC-empty filtering fast from the index while preserving a trustworthy, user-controlled file-metadata verification path.

## Proposed Scope

- Render an immediate SQLite-derived IPTC-empty result.
- Schedule a background file-metadata crosscheck without changing that result automatically.
- Repair detected index discrepancies and expose normal status feedback.
- Add `:resync` to apply the completed verified result atomically.
- Preserve intentional post-activation tag mutations and failure behavior.

## Required Triage Before Implementation

- Verification lifecycle, progress, cancellation, and stale-result rules.
- Index-repair and mutation-race semantics.
- `:resync` availability and feedback.

## Comments

Created from the product backlog. The existing IPTC-empty filter remains authoritative until this ticket is fully triaged.
