# 01 — Build and review the real-file integration suite

Status: needs-info
Category: testing
Priority: high
Milestone: M9 — Repeatable real-file acceptance
Blocked by: maintainer confirmation of test seams in ../spec.md

## Goal

Deliver the bounded subproject in [the specification](../spec.md) so the maintainer
can repeat metadata acceptance without manual fixture setup, copy/paste or cleanup.

## Next action

Confirm the public UI/propagation seams and independent real-file observations.
Then inspect production construction/injection and installed dependencies, record
an implementation plan, and deliver one working vertical slice at a time.

## Acceptance

- [ ] Generated temporary JPEG fixtures and isolated settings/index/workspace.
- [ ] Real ExifTool exercised through production workflow at confirmed seams.
- [ ] Cancel/confirm, subset, canonical IPTC/XMP, backups and persistence coverage.
- [ ] External-change/missing-file rejection and Windows partial-failure/retry.
- [ ] Explicit runner fails on missing required dependencies; useful evidence report.
- [ ] Guaranteed cleanup, bounded waits and no original-photo access.
- [ ] Documented one-command Windows run and minimal visual smoke checklist.
- [ ] Review recorded, findings addressed and existing suite/lint still passing.

## Comments

Maintainer requested this subproject after accepting M8 rather than continuing
repetitive manual tests. Tests have not been written pending seam confirmation.
