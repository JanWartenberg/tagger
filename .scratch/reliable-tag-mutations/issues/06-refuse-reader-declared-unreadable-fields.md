# 06 — Refuse Reader-Declared Unreadable Fields

Status: completed
Category: bug
Priority: high

Routine add/remove/paste and intent retry must refuse a required field reported
unreadable by the metadata reader, without invoking the writer or creating a
backup. Preserve partial successes, explicit failed-only retry, external tags,
pending intent, canonical IPTC and intentionally empty XMP. Explicit Resolve
choices remain deliberate replacements, including their retries.

## Implementation

Validate transformed field readability before any write. Ordinary transforms
retain source readability; explicit Resolve replacements supply chosen readable
states. Both fields are required for routine edits: IPTC supplies tag truth and
XMP determines whether its mirror stays intentionally empty.

Only production change: `tagger_app/services/tag_mutation.py`. No production UI,
worker or lifecycle changes; the Qt characterization test file may overlap the
separate Qt crash investigation. Do not integrate that branch implicitly.

## Validation

The original mock reproduction invoked the writer with `['new']` for both fields
and reported success despite `iptc_readable=False`. Before the fix, the focused
service suite had 48 new failures and 8 passes. Afterward, service, pending-intent
and coordinator tests passed (72 tests). The new Qt test verifies mixed-batch
restoration, refusal of an unreadable retry, failed-only success after repair,
external tags and empty XMP.

Full Linux offscreen pytest: 475 passed, 4 Windows skips, 33 subtests passed.
Ruff lint, modified-file formatting and whitespace checks passed. Real-file
matrix: 18 phases / 50 cases passed in both backup modes, independently inspected
`tests/acceptance/reports/20261021T190859.443782Z/report.json`; all exits, cleanup,
workspace removal and harness hashes verified. Two bounded independent review
passes and final fixture review found no blockers. See `tests/acceptance/REVIEW.md`.

## Limitations

This guard cannot detect malformed data the reader reports as readable. A real
malformed-IPTC replacement was independently reproduced during investigation;
see issue 07. This ticket does not claim general malformed-file safety.

Windows execution/sharing locks/native cleanup remain unrun for this patch;
portable service acceptance does not validate them. The expanded Windows matrix
requires the documented acceptance command when a Windows environment is available.
No visible UI behavior/layout change requires repeated subjective acceptance.

## Integration authorization — 2026-10-21

Jan authorized a further review, commit and main integration. The fresh
independent review found no blocking findings and passed 72 focused tests.
Ruff passed; full offscreen pytest passed again with 475 tests, four Windows
skips and 33 subtests after an initial Qt construction segfault on the unchanged
code. The crash remains part of the separate investigation, not this fix.
The existing inspected 50-case real-file report still matches the harness.
No push authorized.
