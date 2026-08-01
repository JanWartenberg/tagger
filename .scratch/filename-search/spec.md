# Filename Search Within the Photo Workspace

Status: needs-triage
Priority: medium

## Problem Statement

TAGGER can search indexed tags and capture dates, but it has no defined way to narrow the current Photo Workspace by photo filename. Users need to find photos such as names containing `DSC` without replacing the current workspace with an index-wide result.

## Desired Outcome

Define a filename-search workflow that filters the current Photo Workspace by filename while preserving its existing view, selection, and restoration semantics.

## Proposed Direction

A `file:` query form may share the existing tag/date search field, for example `file:DSC`. This is a proposal only; triage must decide the query surface and semantics before implementation.

## Out of Scope

- Searching filenames outside the current Photo Workspace.
- Replacing the existing indexed tag/date search semantics without an explicit decision.
