# Date Search and Range Filters

Status: needs-triage
Priority: medium

## Problem Statement

TAGGER currently accepts `date:<substring>` in the indexed search field. The SQLite index stores the raw displayed capture date, so year/month/day matching depends on the ExifTool string format and no explicit inclusive date-range query exists.

## Desired Outcome

Give the keyboard-driven Photo Workspace a documented, predictable way to find photos by capture year, month, day, and inclusive date range. Results must use the existing temporary database-search view and its persistent files-pane view indicator rather than introducing another result mechanism.

## Existing Baseline

- `PhotoIndex.search_photos()` handles `date:` through a substring `LIKE` query over `photos.date_taken`.
- `photos.date_taken` is populated from `KeywordState.date_display`, which currently retains the selected ExifTool capture/create date string.
- `PhotoWorkspaceViewMode.DATABASE_SEARCH` already renders and restores temporary indexed result views.

## Open Triage Decisions

1. Define the accepted grammar. Candidate forms are `date:YYYY`, `date:YYYY-MM`, `date:YYYY-MM-DD`, and `date:YYYY-MM-DD..YYYY-MM-DD`.
2. Decide whether partial dates mean calendar periods and whether a range's endpoints are inclusive.
3. Decide the canonical indexed date representation. A normalized sortable capture-date value may be required for reliable day/month/range queries; retain the displayed date independently if necessary.
4. Define behavior for missing, malformed, timezone-bearing, and create-date-fallback metadata.
5. Decide whether date filtering remains command/search-field syntax only or adds a dedicated date control. The default recommendation is syntax only.
6. Decide validation and user feedback for invalid date expressions.

## Constraints

- SQLite and metadata work remain off the Qt UI thread through the existing coordinator seam.
- The active-root scope, stale completion rules, and folder-view restoration of indexed search remain unchanged.
- Do not overload the IPTC-empty filter state; date results are database-search views.
- Any index migration or backfill must preserve existing tag search and index freshness behavior.

## Out of Scope

- Global cross-root search.
- File modification-date filtering unless explicitly chosen during triage.
- Calendar UI, timeline visualisation, or saved searches.
