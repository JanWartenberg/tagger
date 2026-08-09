# Keyword Length Limits

Status: ready-for-agent
Priority: medium

## Problem Statement

TAGGER writes `IPTC:Keywords` and, where present, `XMP-dc:Subject`. A keyword that exceeds the IPTC IIM limit can be silently truncated by ExifTool, leaving the two fields inconsistent and losing user data.

## Resolved Policy

- An IPTC keyword is valid only when its NFC-normalized, outer-whitespace-trimmed UTF-8 encoding is at most **64 bytes**. The limit applies to each keyword, not to the complete list.
- XMP has no corresponding practical per-keyword limit, but TAGGER must not copy an over-limit XMP value into IPTC.
- Reject rather than truncate or merely warn at every user-facing insertion and at the final write boundary. Existing user text and source metadata remain intact on rejection.
- Routine TAGGER writes retain the established IPTC/XMP policy: an intentionally empty XMP field stays empty; a non-empty XMP field mirrors the approved IPTC keyword set.

## Evidence

- [IPTC Photo Metadata Standard 2025.1: Keywords](https://www.iptc.org/std/photometadata/specification/IPTC-PhotoMetadata-2025.1.html#keywords) maps IIM dataset `2:25 Keywords` to a maximum of 64 text bytes.
- [IPTC: Max bytes for text](https://www.iptc.org/std/photometadata/specification/IPTC-PhotoMetadata-2025.1.html#max-bytes-for-text) clarifies that this is bytes, not characters, and UTF-8 non-ASCII characters consume multiple bytes.
- [ExifTool IPTC tag table](https://github.com/exiftool/exiftool/blob/2200871d9cef988051d2a99d67df3bda6cbb30a8/lib/Image/ExifTool/IPTC.pm#L319-L323) defines `Keywords` as `string[0,64]`; its [IPTC writer](https://github.com/exiftool/exiftool/blob/2200871d9cef988051d2a99d67df3bda6cbb30a8/lib/Image/ExifTool/WriteIPTC.pl#L188-L205) warns and truncates after character-set conversion.

## Approved Interaction

- The Add Keyword field warns live once the normalized value exceeds the limit: its text/border turns red, its Add button is unavailable, and the normal footer reports the current UTF-8 byte count.
- A submit attempt through Enter, Ctrl+Enter, the button, or `:addtag` is rejected defensively: focus remains in the field, its unmodified text remains available for editing/copying, and no pending mutation or recent tag is created.
- Known-tag activation and yanked-tag paste validate their candidate lists before queuing. They normally contain previously written IPTC tags, but remain guarded against malformed external metadata.
- In Resolve, an XMP-to-IPTC single copy is rejected in place when over the limit. A whole-list XMP-to-IPTC copy is atomic: if any candidate is invalid, no value is copied and the dialog explains why. Apply performs the same final validation and leaves the dialog open on rejection.

## Constraints

- The validation rule must have one pure, Qt-free implementation shared by UI preflight, Resolve, mutation services, and the ExifTool write adapter.
- Preserve TAGGER's synchronized IPTC/XMP keyword-write behavior unless a separately approved change is required.
- No tag-import or command-argument insertion endpoint currently exists; the covered paths are manual input, Known Tags, yanked-tag paste, and Resolve copying.
