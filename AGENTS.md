# Repository guidance

## Engineering expectations

- Write repository artifacts, documentation, comments, and user-facing text in English.
- Default to concise UI labels and minimal persistent explanatory text. Put optional detail in tooltips or help; keep essential state, errors and confirmation information visible.
- TAGGER is a local personal tool. No additional compliance, tenancy, or remote-data security requirements apply.
- TAGGER is a Python and PyQt desktop tool developed primarily for Windows; keep it compatible with Linux where practical.
- Keep the UI responsive by human standards. Potentially long-running work must run in the background rather than block the UI thread.
- Use Ruff to lint and format new or modified Python code. Do not reformat unrelated legacy code as part of a focused change.
- Before handing off Python changes, run `ruff check .` and `QT_QPA_PLATFORM=offscreen pytest` from an activated development environment; use the Windows equivalents documented in `tests/README.md` on Windows.

## Agent-owned acceptance

- Own automated verification: implement, run relevant tests, inspect evidence, fix failures and report results without asking the maintainer to perform steps available in the agent's environment.
- Reuse the real-file acceptance suite in `tests/acceptance/` for changes affecting its covered workflows. Read `tests/acceptance/README.md`; run `python tests/acceptance/run.py` from the repository root in the development environment. This is a separate command from pytest.
- The suite covers tag copying, cancellation, selected targets, canonical IPTC/XMP, backups, persistence, changed/missing-file refusal and failed-only retry. Existing cases do not automatically validate new features; add focused scenarios when behavior changes require them.
- Reuse its generated disposable JPEGs, isolated settings/indexes, real ExifTool, public Qt interactions, bounded waits, process cleanup and diagnostic reports when extending acceptance. Do not use personal photos or desktop-wide input automation.
- Run portable coverage locally. Windows sharing-lock and native process-cleanup checks require a Windows environment; Linux results do not validate them. If Windows execution is unavailable, request only the necessary Windows run and inspect its report when accessible. Distinguish maintainer-reported results from independently inspected evidence.
- Reserve maintainer involvement for subjective visual acceptance, unresolved product decisions and checks unavailable in the agent's environment. Automate observable behavior where practical; do not repeat previously accepted manual checks unless a relevant change invalidates them.
- Record acceptance and remaining limitations in the affected tickets/status docs and `tests/acceptance/REVIEW.md`; update `VISUAL_SMOKE.md` when its checks are affected. Distinguish passed, waived and unrun checks. Acceptance does not itself authorize a commit, merge or push.

## Agent skills

### Issue tracker

Issues and specs use local Markdown under `.scratch/`. See `docs/agents/issue-tracker.md`.

### Triage labels

The repository uses the five default triage labels. See `docs/agents/triage-labels.md`.

### Domain docs

This is a single-context repository using root `CONTEXT.md` and `docs/adr/`. See `docs/agents/domain.md`.
