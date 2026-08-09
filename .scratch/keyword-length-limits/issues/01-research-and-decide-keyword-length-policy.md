# 01 — Research and Decide Keyword-Length Policy

Status: completed
Priority: medium
Category: research
Milestone: M3 — Metadata integrity and cache-backed IPTC workflow
Blocked by: None

## Goal

Determine metadata and ExifTool keyword-length limits, then record TAGGER's validation policy.

## Resolution

- IPTC IIM dataset `2:25 Keywords` permits at most 64 bytes per keyword; the current IPTC standard explicitly distinguishes bytes from characters under UTF-8.
- `XMP-dc:Subject` has no matching practical per-value limit, but TAGGER's IPTC write makes the 64-byte limit the compatibility constraint.
- ExifTool represents IPTC Keywords as `string[0,64]` and truncates over-limit values after character-set conversion. TAGGER will reject rather than permit that loss.
- Approved product policy and evidence: [`../spec.md`](../spec.md).
- Follow-up implementation: [`02-enforce-iptc-keyword-byte-limit.md`](02-enforce-iptc-keyword-byte-limit.md).

## Comments

Created from `BACKLOG.md`. No priority was recorded there.

Triage completed: enforce the 64-byte UTF-8 IPTC limit with live input feedback and final write-boundary validation.
