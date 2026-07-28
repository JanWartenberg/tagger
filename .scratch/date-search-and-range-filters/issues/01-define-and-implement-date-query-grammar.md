# 01 — Define and Implement Date Query Grammar

Status: ready-for-agent
Category: feature
Priority: medium
Blocked by: None

## Goal

Define and deliver reliable indexed capture-date queries for calendar periods and date ranges, using the existing database-search result view.

## Scope

- Support `date:YYYY`, `date:YYYY-MM`, `date:YYYY-MM-DD`, `date:YYYY-MM-DD..YYYY-MM-DD`, and `date:unknown`.
- Treat year and month queries as complete calendar periods; require full valid dates in ranges and include both endpoints. Reject open-ended or partial-date ranges.
- Define capture date as `EXIF:DateTimeOriginal`, falling back to `EXIF:CreateDate`; do not alter its calendar day for time or timezone data.
- Store a separate nullable normalized `YYYY-MM-DD` capture-date column. Migrate and backfill it from the existing raw `photos.date_taken` values; unparseable and missing values are date-unknown.
- Preserve `tag:` and bare-tag query behavior.
- Keep date filtering in the search field and `:search`; invalid date expressions leave the active Photo Workspace unchanged and show clear status feedback.
- Route valid reads through `BackgroundCoordinator.search_index()` and render results through the existing database-search view and files-pane view indicator.

## Initial Test Expectations

- Unit tests for accepted and rejected expressions, calendar boundaries, inclusive ranges, missing/unparseable dates, source fallback, migration backfill, and legacy raw values.
- Coordinator and offscreen tests for valid result restoration and visible active-query feedback, plus invalid input that preserves the current Photo Workspace and does not schedule a search.

## Triage Record

Triage completed: the grammar, date-source priority, unknown-date semantics, normalized-index migration, syntax-only interaction, and invalid-input behavior are fixed by `.scratch/date-search-and-range-filters/spec.md` and `docs/adr/0001-capture-date-query-semantics.md`.

## Validation

- Extend the validation file list after triage identifies the schema and adapter changes.
- `QT_QPA_PLATFORM=offscreen python3 -m unittest discover -s tests -v`
- `git diff --check`
