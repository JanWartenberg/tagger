# Real-file acceptance — delivery plan

Approved seams: public MainWindow entrypoints and real Qt events, production
ExifTool/discovery/index/background execution, independent ExifTool CLI JSON and
file hashes. No private widget state or database assertions.

1. Verify dependencies and JPEG generation. Isolate APPDATA, HOME, Qt settings,
   cache and photo/index workspace before constructing MainWindow.
2. Generate two JPEGs with equal capture timestamps, one tagged source and one
   empty target. Discover, scan, select source, preview, confirm, and observe
   completion. Independently verify canonical IPTC and mirrored XMP, unchanged
   source, changed target, and readable JPEGs.
3. Keep bounded event-loop waits, subprocess deadlines, worker draining and
   temporary-workspace cleanup. Preserve diagnostics outside cleanup.
4. Review this slice; run Ruff and the full existing offscreen suite.

## Status

- Slice 1: complete; Linux and maintainer Windows confirmed-copy reports retained.
- Slice 2: cancellation, subsets, canonical IPTC/existing-XMP and empty-XMP policy,
  backups off/on and fresh-process metadata persistence implemented and checked on
  Linux and Windows (`reports/20261002T152911.296728Z`).
- Process containment: native Windows cleanup probes and normal matrix passed
  (`reports/20261002T162912.910988Z`).
- Slice 3: real changed/missing source/target refusals at preview/confirmation,
  final target-write guard, and native sharing-lock partial failure/failed-only
  UI retry implemented. Portable cases pass on Linux; native Windows lock/retry
  passed in the previously verified expanded Windows reports.
- Full expanded Windows matrix passed twice on fa2be3f (32 results each).
- Scan setup collapse, actionable-only default/all-candidates toggle, and shared
  candidate photo menu are now implemented (follow-ups 02b/02c/02d).
- Complete: maintainer reported Windows runner PASSED for the footer revision
  (`reports/20261004T112405.399638Z/report.json`) and accepted remaining
  visual checks on 2026-10-04. Larger-font testing was explicitly waived; window
  scaling passed. M9 is closed. See `REVIEW.md` for evidence and acceptance limits.

Slice 2 uses four generated photos per backup setting: a tagged source with a
conflicting XMP mirror, two selected empty-IPTC targets (one existing XMP mirror,
one empty XMP), and one excluded eligible target. Cancel and confirm are exercised
through real Qt events. Backup bytes are checked against pre-write full hashes.
After the writer exits, a separate reader process loads each selected target in a
fresh MainWindow and checks visible tags plus independent metadata/file hashes.

Previous manual JPEGs and their .tagger directory are preserved in ignored
`local-fixtures/` and are not inputs to automation. Harness code now lives in
`tests/acceptance/` in TAGGER; reports remain here and are ignored by Git.
No artificial production failure is required: record genuine harness failures
and the eventual run against working production code.
