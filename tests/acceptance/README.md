# TAGGER real-file acceptance

Explicit real-file matrix using generated JPEGs, production discovery/index and
ExifTool, public Qt events, independent metadata/hash checks and fresh-process UI
reads. No production adapters are replaced; pytest does not collect this harness.

## Run

Requires Python 3.11+, Git and ExifTool on PATH, plus `requirements-dev.txt`.
No extra image library or pytest plugin is needed; Qt generates JPEGs.
Run from the **repository root**.

Windows PowerShell:

```powershell
# First-time setup only; reuse the project environment if available.
py -3 -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements-dev.txt
.\.venv\Scripts\python tests\acceptance\run.py
```

Linux, using an activated development environment:

```sh
python tests/acceptance/run.py
```

For a fresh Linux environment (Debian also needs `python3-venv` and `libgl1`):

```sh
python3 -m venv /tmp/acceptance-venv
/tmp/acceptance-venv/bin/python -m pip install -r requirements-dev.txt
/tmp/acceptance-venv/bin/python tests/acceptance/run.py
```

Do not move/reuse the old sibling-folder virtual environment; recreate it.
The runner sets offscreen Qt itself and accepts no photo-directory arguments.
Missing dependencies, failed assertions or timeouts produce a nonzero exit.
Python `-O`/`PYTHONOPTIMIZE` is rejected.

## Coverage

Each run checks both backup settings in separate disposable workspaces:

| Case | Independent checks |
| --- | --- |
| Cancel | All four JPEG hashes unchanged; no new files/backups |
| Confirm selected subset | Two targets change; source and excluded target unchanged |
| Canonical IPTC/XMP | Source-only XMP tags are not copied; existing target XMP mirrors IPTC; empty XMP remains empty |
| Backups off/on | No backups when off; exactly two byte-identical original backups when on |
| Persistence | Writer exits; a separate process displays saved tags and rereads metadata; JPEGs/backups unchanged |

All eight case results across four process phases are required. Missing results
or failed phases fail the command, not an all-skipped pass.
The expanded matrix passed on Windows before relocation:
`reports/20261002T152911.296728Z/report.json`. Rerun the new command on Windows.

## Isolation and evidence

- Previous manual JPEGs and their index are preserved in ignored `local-fixtures/`;
  automation never reads them.
- Generated photos, settings and indexes live in disposable OS temporary directories.
  APPDATA/HOME/config/cache are redirected before MainWindow construction.
- Qt events go only to the child's own offscreen widgets, not the desktop.
- Assertions use public widget outcomes, independent ExifTool reads, file hashes
  and JPEG decoding, not private state or index tables.
- Event-loop waits are bounded at 20 seconds, CLI calls at 15 seconds, and each
  child at 120 seconds. Workers drain before normal shutdown; POSIX process-group
  termination handles hung children and descendants.
- `reports/<timestamp>/` preserves JSON and separate phase stdout/stderr logs,
  source commit/worktree, harness hashes, dependencies, process IDs and observations.
- Harness code/docs are tracked in TAGGER. Reports and local fixtures are ignored;
  preserve useful evidence separately before discarding the workspace.

## Remaining work

Changed/missing-file refusal and Windows sharing-lock partial-failure/retry are
not implemented. Persistence covers metadata, not backup preferences or last view.
No visual acceptance has been run. Windows has a taskkill timeout fallback, but
abrupt-exit orphan cleanup still needs strengthening and Windows validation.
Successful normal runs do not establish full-suite acceptance or guaranteed
Windows cleanup. See `PLAN.md` and `REVIEW.md`.
