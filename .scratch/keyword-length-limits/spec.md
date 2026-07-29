# Keyword Length Limits

Status: needs-triage

## Problem Statement

TAGGER does not document whether IPTC, XMP, or ExifTool impose practical keyword-length limits, so validation behavior is undefined.

## Desired Outcome

Establish the applicable technical limits and decide whether TAGGER should validate, warn, enforce a limit, or leave input unrestricted.

## Open Triage Decisions

- Authoritative limits by metadata format and ExifTool behavior.
- Cross-format behavior when the limits differ.
- Product response: no validation, warning, or enforcement, including user-facing wording.

## Constraints

- Preserve TAGGER's synchronized IPTC/XMP keyword-write behavior unless a separately approved change is required.
