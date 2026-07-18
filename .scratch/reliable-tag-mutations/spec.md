# Reliable Tag Mutations

Status: needs-triage
Priority: high

## Problem Statement

TAGGER updates cached metadata and the visible UI before ExifTool confirms a write. A failed or partially failed queued mutation can leave the Photo Workspace presenting tags that were not persisted to the photo files.

## Solution

Make queued tag mutations explicitly reliable: preserve responsive feedback while distinguishing pending from confirmed metadata and recovering the UI, cache, index, and IPTC-empty visibility after failure.

## User Stories

1. As a TAGGER user, I want a failed tag write to be clearly reported, so I do not trust metadata that was not saved.
2. As a TAGGER user, I want the displayed tags to return to confirmed file state after a failed write.
3. As a TAGGER user, I want later queued edits to have deterministic behavior after an earlier edit fails.
4. As a TAGGER user, I want multi-photo writes to report which photos succeeded or failed.
5. As a maintainer, I want tag, cache, index, and IPTC-empty filter updates to share one confirmed result.

## Implementation Decisions

- Retain background execution and ordered mutation processing.
- Model pending and confirmed metadata distinctly enough that failure cannot silently become displayed truth.
- Define the result contract for complete success, complete failure, and partial success before applying UI or index changes.
- Make the index reflect only confirmed persisted metadata.
- Keep Photo Workspace responsible only for visibility rules based on confirmed emptiness facts.

## Testing Decisions

- Test mutation coordination with a fake metadata writer that succeeds, fails, and partially fails.
- Assert observable cache/UI/index/filter outcomes rather than queue internals.
- Keep direct tag transformation tests independent from Qt and ExifTool.
- Add offscreen adapter coverage for visible error recovery.

## Out of Scope

- New tagging workflows, tag suggestions, or changes to IPTC/XMP formats.

## Further Notes

Grilling is required before tickets: settle optimistic-update policy, retry policy, partial-batch UX, and the behavior when files change externally while mutations are queued.