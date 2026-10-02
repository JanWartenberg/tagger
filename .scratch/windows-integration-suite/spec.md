# Windows real-file integration suite

Status: needs-info
Priority: high
Milestone: M9 — Repeatable real-file acceptance
Blocked by: maintainer Windows UI regression and visual acceptance

## Goal

Replace repeated terminal/app acceptance choreography with one reproducible command
that exercises TAGGER against disposable JPEGs and real ExifTool. Treat this as a
bounded subproject, not a new testing framework or an application rewrite.

## Confirmed seams

1. Public MainWindow entrypoints and actual Qt widget/key events: scan, source and
   target selection, preview, cancel/confirm, backup toggle, outcomes and retry.
   Use production ExifTool and background execution, not fake metadata/mutation
   adapters. Isolate preferences, discovery, index and all writes to a temporary
   workspace; identify any necessary dependency injection during implementation.
2. Public propagation/mutation interfaces with real files for safety cases not
   reliably reachable through UI timing. Existing fake-adapter tests remain the
   deterministic coverage for pending intent and superseded-navigation races.
3. Independent observations: ExifTool CLI JSON reads, full JPEG hashes, backup
   contents/existence. No private widget internals or production databases used
   as assertion shortcuts.

## Delivery slices

- Establish isolated, generated valid JPEG fixtures (no personal photos needed),
  explicit dependency checks and guaranteed process/lock cleanup. Prove one real
  confirmed copy through the agreed seam.
- Add cancellation/no-write behavior, target subsets, IPTC/XMP canonical results,
  backups on/off and fresh application/read persistence.
- Add changed source/target and missing-file refusal; exercise partial failure and
  failed-only retry with an OS-level sharing lock on Windows, not mocked writes.
- Publish a one-command runner, evidence/report output and a short visual checklist;
  review changes and fix findings before handoff.

## Constraints and acceptance

- Never accept a user photo-directory input; generate fixtures in temporary roots.
- Real ExifTool must be required in the explicit integration command. Missing
  dependencies must fail that command clearly, not yield a green all-skipped run.
- Ordinary unit/adapter suite remains fast and independent of ExifTool installation.
- Use bounded event-loop waits on observable state; avoid sleep-based race guessing.
- Windows lock case must release handles in finally/cleanup; label platform-only
  coverage honestly on Linux. Passing Linux does not claim Windows validation.
- Write artifact reports outside fixture cleanup with command, commit, platform,
  dependency versions, case results and useful failure diagnostics. No original
  photo data or persistent user settings may be touched.
- One documented command performs setup, execution, assertions and cleanup. Manual
  acceptance is limited to visual navigation/contrast/layout, including collapsible
  Scan setup; do not mark these passed based on headless checks.
- Keep each implementation slice reviewed and run Ruff plus the existing full
  suite. Retain honest red/green evidence; do not fabricate failures in working
  production behavior merely to satisfy a test-first workflow.

## Dependencies and decisions

M8 was accepted by maintainer with remaining manual coverage waived. No main-branch
merge is authorized by that acceptance. The maintainer approved real ExifTool
and temporary JPEGs after clarification that Qt events remain within the test's
own offscreen application, with no desktop-wide mouse/keyboard control.
The refreshed Docker container has ExifTool 12.57 (Debian
`libimage-exiftool-perl`), verified by the maintainer. Recheck dependencies after
session reload and determine fixture-generation support before selecting extra
test dependencies. Do not assume a Windows host is available here.

## Issues

- [01 — Build and review the real-file integration suite](issues/01-build-real-file-integration-suite.md)
