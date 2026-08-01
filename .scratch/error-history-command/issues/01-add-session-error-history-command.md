# 01 — Add Session Error History and `:errors`

Status: needs-triage
Category: feature
Priority: low
Milestone: M2 — Reliable, scalable index operations
Blocked by: None

## Goal

Let users review timestamped tool errors from the current TAGGER session without interrupting normal non-modal feedback.

## Required Triage Before Implementation

- Define recorded error classes, displayed detail, ordering, and retention.
- Define `:errors` empty-state and command-catalogue behavior.
- Confirm that history is session-only.

## Comments

Created from `BACKLOG.md`; deliberately separate from the completed background discovery and index-I/O work.
