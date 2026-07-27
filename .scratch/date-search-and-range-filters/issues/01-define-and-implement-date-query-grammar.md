# 01 — Define and Implement Date Query Grammar

Status: needs-triage
Category: feature
Priority: medium
Blocked by: None

## Goal

Define and deliver reliable indexed capture-date queries for calendar periods and date ranges, using the existing database-search result view.

## Proposed Scope After Triage

- Specify the supported year, month, day, and inclusive range expressions.
- Normalize or otherwise query indexed capture dates so the grammar is independent of raw ExifTool display formatting.
- Preserve `tag:` and bare-tag query behavior.
- Route reads through `BackgroundCoordinator.search_index()` and render results through the existing database-search view.
- Present the active date expression through the files-pane view indicator.

## Required Triage Before Implementation

- Final grammar and range separator.
- Inclusivity, incomplete range endpoints, and invalid-expression behavior.
- Canonical capture-date value and migration/backfill strategy for existing indexes.
- Missing-date and timezone/create-date fallback semantics.
- Whether a search-field-only interaction is sufficient.

## Initial Test Expectations

- Unit tests for accepted and rejected expressions, boundary dates, calendar periods, missing dates, and ranges.
- Coordinator and offscreen tests for stale reads, result restoration, and visible active-query feedback.

## Validation

- Extend the validation file list after triage identifies the schema and adapter changes.
- `QT_QPA_PLATFORM=offscreen python3 -m unittest discover -s tests -v`
- `git diff --check`
