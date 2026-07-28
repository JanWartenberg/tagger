# Date Search and Range Filters

Status: ready-for-agent
Priority: medium

## Problem Statement

TAGGER currently accepts `date:<substring>` in the indexed search field. The SQLite index stores the raw displayed capture date, so year/month/day matching depends on the ExifTool string format and no explicit inclusive date-range query exists.

## Desired Outcome

Give the keyboard-driven Photo Workspace a documented, predictable way to find photos by capture year, month, day, and inclusive date range. Results must use the existing temporary database-search view and its persistent files-pane view indicator rather than introducing another result mechanism.

## Existing Baseline

- `PhotoIndex.search_photos()` handles `date:` through a substring `LIKE` query over `photos.date_taken`.
- `photos.date_taken` is populated from `KeywordState.date_display`, which currently retains the selected ExifTool capture/create date string.
- `PhotoWorkspaceViewMode.DATABASE_SEARCH` already renders and restores temporary indexed result views.

## Resolved Decisions

- A **capture date** comes from `EXIF:DateTimeOriginal`, with `EXIF:CreateDate` as its fallback. Its stored time or timezone does not change its calendar day.
- The accepted expressions are `date:YYYY`, `date:YYYY-MM`, `date:YYYY-MM-DD`, `date:YYYY-MM-DD..YYYY-MM-DD`, and `date:unknown`. Years have four digits; months and days must be valid zero-padded calendar values. Ranges require two full dates; open-ended and partial-date ranges are invalid.
- Year and month expressions mean their complete calendar period. Full-date range endpoints are inclusive.
- `date:unknown` returns photos with no source date and photos whose source date cannot be normalized. It supports metadata counterchecks and correction work.
- Store a separate normalized nullable capture-date value as `YYYY-MM-DD`; retain the existing raw `photos.date_taken` value for legacy compatibility. Add the new column through a SQLite migration and backfill it by normalizing existing raw values; values that cannot be normalized become date-unknown until a later index refresh supplies valid metadata.
- Date filtering remains search-field and `:search` syntax only. Invalid date expressions do not schedule a search or change the active Photo Workspace; they produce clear status feedback.

## Constraints

- SQLite and metadata work remain off the Qt UI thread through the existing coordinator seam.
- The active-root scope, stale completion rules, and folder-view restoration of indexed search remain unchanged.
- Do not overload the IPTC-empty filter state; date results are database-search views.
- Any index migration or backfill must preserve existing tag search and index freshness behavior.

## Out of Scope

- Global cross-root search.
- File modification-date filtering unless explicitly chosen during triage.
- Calendar UI, timeline visualisation, or saved searches.
