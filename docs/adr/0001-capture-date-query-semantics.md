# Capture-date query semantics

Status: accepted

Date queries use the EXIF capture date (`EXIF:DateTimeOriginal`, falling back to `EXIF:CreateDate`) as an unconverted calendar day. The index stores a separate nullable `YYYY-MM-DD` capture-date value, while retaining the raw legacy date value for migration compatibility. This makes year, month, day, and inclusive full-date range queries independent of ExifTool display formatting; missing or unparseable values are deliberately searchable with `date:unknown` so they remain available for metadata correction.

## Considered Options

- Continue substring-matching ExifTool's raw display value. Rejected because its format cannot provide dependable calendar-period or range semantics.
- Convert timestamps to another timezone before indexing. Rejected because date search is defined by the recorded capture calendar day, not by an inferred instant.
