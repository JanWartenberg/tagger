# Repository guidance

## Engineering expectations

- Write repository artifacts, documentation, comments, and user-facing text in English.
- TAGGER is a local personal tool. No additional compliance, tenancy, or remote-data security requirements apply.
- TAGGER is a Python and PyQt desktop tool developed primarily for Windows; keep it compatible with Linux where practical.
- Keep the UI responsive by human standards. Potentially long-running work must run in the background rather than block the UI thread.
- Use Ruff to lint and format new or modified Python code. Do not reformat unrelated legacy code as part of a focused change.

## Agent skills

### Issue tracker

Issues and specs use local Markdown under `.scratch/`. See `docs/agents/issue-tracker.md`.

### Triage labels

The repository uses the five default triage labels. See `docs/agents/triage-labels.md`.

### Domain docs

This is a single-context repository using root `CONTEXT.md` and `docs/adr/`. See `docs/agents/domain.md`.
