# TAGGER real-file acceptance

Explicit real-file matrix using generated JPEGs, production discovery/index and
ExifTool, public Qt events, independent metadata/hash checks and fresh-process UI
reads. No production adapters are replaced. Pytest collects process-control tests,
not the real-file matrix.

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
| Preview/confirmation refusal | Changed or missing source/target rejected after a positive unchanged-file control; all remaining file bytes and file sets unchanged |
| Final target write guard | Changed/missing target is reported failed without metadata or backup writes |
| Persistent ignores | Ignore survives a fresh process; inspecting previews/evidence does not restore; explicit restore and confirmed clear-all persist; changed capture provenance returns the candidate; all application actions leave JPEG hashes/file sets unchanged |
| Windows sharing lock | Real read-only sharing handle permits reads but denies writes/deletion; one target succeeds, one fails; explicit retry changes only the failed target after releasing the lock |

Both backup settings are required. Linux requires 38 case results across fourteen
process phases. Windows requires 42 results across sixteen phases plus the native
cleanup probes. Missing results or failed phases fail the command, not an
all-skipped pass. Linux explicitly reports Windows-only coverage as not run.
Safety phases use public propagation/mutation services, without timing races;
sharing-lock failure/retry uses public UI events and real production workers.
The expanded matrix passed on Windows before relocation:
`reports/20261002T152911.296728Z/report.json`, and after relocation:
`reports/20261002T161141.558457Z/report.json`.

Windows runs now also require native cleanup probes: timeout with a descendant,
abrupt child exit with a surviving descendant, kill-on-job-handle-close, and
assignment refusal before script execution. Their logs are `cleanup-stdout.txt`
and `cleanup-stderr.txt`; the report records `windows_process_cleanup`. Linux
explicitly reports these Windows-only probes as not run. These cleanup probes
passed on Windows in `reports/20261002T162912.910988Z/report.json`; that run
predates the new refusal and sharing-lock cases.

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
  termination handles hung children and descendants. Windows uses a non-inheritable
  kill-on-close Job Object: the script cannot run until assignment succeeds, and
  shutdown terminates the job and waits for its active process count to reach zero.
- `reports/<timestamp>/` preserves JSON and separate phase stdout/stderr logs,
  source commit/worktree, harness hashes, dependencies, process IDs and observations.
- Harness code/docs are tracked in TAGGER. Reports and local fixtures are ignored;
  preserve useful evidence separately before discarding the workspace.

## Acceptance and reuse

M9 is completed by maintainer acceptance on 2026-10-04. The maintainer reported
Windows runner PASSED in `reports/20261004T112405.399638Z/report.json` and accepted
the remaining [visual checks](VISUAL_SMOKE.md). Larger-font testing was explicitly
waived; window scaling passed. See `REVIEW.md` for evidence and acceptance limits.

Reuse this command for regression checks of covered workflows and add focused
cases for new behavior. Linux validates portable refusal cases, not native
sharing locks. Persistence covers metadata, not backup preferences or last view.
Automated reports do not replace subjective visual acceptance or authorize
main-branch integration. See `PLAN.md` and the repository `AGENTS.md`.
