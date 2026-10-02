# Slice 1 review and execution record

Reviewed only this subproject's `run.py` and `confirmed_copy.py` against the
approved MainWindow/Qt-event and independent-file-observation seams. TAGGER's
pre-existing dirty ticket/spec/BACKLOG edits were not changed. No production
code changes were needed.

## Findings addressed

- Harness assumed writes create missing XMP. README and mutation policy explicitly
  preserve empty XMP. Seeded an existing target mirror and kept exact canonical
  IPTC/XMP expectations; did not change production behavior to fit a test.
- Space is a duplicate-review command prefix, not a reliable radio-button toggle.
  Changed source selection to an actual mouse event on the radio indicator.
- Optimized Python could remove assertions. Runner now rejects optimization.
- Failure reports initially omitted cleanup status. Cleanup status is now emitted
  for every run that allocated a workspace, including failures.
- Git commit alone cannot identify this untracked harness. Reports now include
  SHA-256 hashes of both harness scripts.

## Execution evidence

Environment: Python 3.11.2, ExifTool 12.57, PyQt 6.11.0, Qt runtime 6.11.2,
Linux/WSL2. Installed Debian python3-venv and libgl1; dev environment installed in
`/tmp/tagger-acceptance-venv` after two workspace-volume installation timeouts.

Preserved genuine failures:

- `reports/20261001T193150.919102Z`: Qt import failed, missing libGL.so.1.
- `reports/20261001T193159.874085Z`: source selection via Space did not enable copy.
- `reports/20261001T193237.034946Z`: wrong missing-XMP expectation after a real write.

Positive runs:

- `reports/20261001T193311.378679Z`, `20261001T193619.818115Z`, and
  `20261001T193624.117658Z`: confirmed-copy passed, workspace removed.
- `reports/20261001T193742.693253Z`: final harness passed, including structured
  observations and harness hashes.

Dependency/guard probes:

- `reports/20261001T193628.652207Z`: empty PATH failed explicitly for missing
  ExifTool, exit 1, no skipped success.
- `reports/20261001T193628.947594Z`: Python -O rejected, exit 1.

Validation:

- Ruff check for TAGGER and harness: passed; harness formatting: passed.
- `reports/existing-suite.txt`: 327 passed, 1 failed, 33 subtests passed.
  The existing preview scheduling test observed photo-0 before photo-4.
- `reports/existing-suite-rerun.txt`: complete rerun, 328 passed, 33 subtests passed.
  No test or production code was changed between these runs. The initial
  timing-sensitive failure is retained, not claimed fixed.

## Open limitations / next slice

- Windows not tested. taskkill covers a still-running timed-out child, but cannot
  guarantee orphan cleanup after abrupt parent-child termination. Add Job Object
  containment and exercise it on Windows before cross-platform cleanup acceptance.
- Hard-timeout/abrupt-exit cleanup paths have not yet been fault-injected; ordinary
  successful and assertion-failed Linux runs cleaned up their workspaces.
- No cancellation/subset/backup/persistence/safety/retry matrix yet; see PLAN.md.
- Offscreen tests say nothing about actual contrast/layout/navigation quality.
- The failed workspace-local venv install was removed as far as the mount allows;
  `.venv/lib/python3.11/site-packages/PyQt6/Qt6/plugins` resisted deletion with
  Permission denied. It is not used. The working environment is under `/tmp`.

# Slice 2 — normal-path matrix

## Prior Windows evidence

The maintainer's report `reports/20261001T202314.789644Z/report.json` confirms the
original confirmed-copy slice passed on Windows 11 with Python 3.14.7, ExifTool
13.59, PyQt 6.11.0 and Qt 6.11.2; its temporary workspace was removed. That report
predates this expanded matrix and does not validate its new cases.

## Delivery and review

1. Added cancellation/no-write checks to the original vertical slice first;
   `reports/20261001T203621.081779Z` passed against unchanged production code.
2. Extended the scenario with an excluded eligible target, two selected targets
   with different XMP states, conflicting source XMP, and backup off/on runs.
3. Added a separate post-writer process for persistence. It opens a fresh window
   for each target, waits for visible canonical tags, independently reads metadata,
   and checks that reopening changed no JPEG or backup bytes.
4. Changed reporting to require all expected case results in every phase, preserve
   per-phase logs/results, record writer/reader process IDs, and report cleanup
   independently for each backup setting's workspace.

Review findings addressed:

- Closed preview dialogs can remain Qt children until deferred deletion: preview
  lookup now requires visibility so the second confirmation cannot target a stale
  cancelled dialog.
- A same-window persistence check could accidentally pass from cached metadata:
  the writer exits before a fresh reader process starts; each target gets its own
  initially empty MainWindow.
- Checking only known JPEGs would miss accidental backups: snapshot all direct
  photo-directory files and require exact file sets, plus backup SHA-256 equality
  to pre-write JPEGs. Only the mutable index directory is excluded.
- Parsing only one passing observation could hide omitted matrix cases: require
  the exact case set per phase and complete both backup settings before success.
- Cross-platform child-log decoding is now explicitly UTF-8.

No new unresolved findings in the normal-path slice. The previously documented
Windows orphan-cleanup limitation remains; do not claim full failure-path
acceptance from successful normal runs. No TAGGER production/test code changed.

## Evidence

- `reports/20261001T203933.773378Z`: initial expanded matrix passed.
- `reports/20261001T204212.676644Z`: repeat expanded matrix passed; four process
  phases, eight case results, both temporary workspaces removed.
- Ruff checks (TAGGER and harness) and harness format check passed.
- `reports/slice-2-existing-suite.txt`: 327 passed, 1 failed, 33 subtests passed;
  the same pre-existing preview scheduling test observed photo-0 before photo-4.
- `reports/slice-2-existing-suite-rerun.txt`: 328 passed, 33 subtests passed.
  No application/test changes were made to obtain the passing rerun; the
  timing-sensitive failure is unresolved and both logs are retained.

No artificial production failure was introduced. The new expectations passed
against existing production behavior. Run `python .\\run.py` on Windows again to
validate this expanded slice. Changed/missing-file and sharing-lock/retry cases
remain the next delivery slice, not part of these results.

# Windows confirmation and repository relocation

- Expanded Windows matrix passed in `reports/20261002T152911.296728Z`; four
  phases passed and both temporary workspaces were removed.
- Harness moved to `tests/acceptance/`; repository lookup and child import paths
  now resolve the repository root from that location. No production changes.
- All historical reports preserved unchanged. Previous manual JPEGs/index moved
  to ignored `local-fixtures/`, not used by automation. Reports are ignored too.
- Relocated Linux matrix passed: `reports/20261002T153826.873517Z`.
- Old sibling-folder removal is blocked by filesystem Permission denied on three
  virtual-environment directories. Only disposable venv remnants remain; delete
  the old folder on Windows. The old environment is no longer usable.
- Ruff check, harness format check and diff whitespace check passed.
- Required pytest command could not run: pytest is absent in this refreshed
  environment (venv creation also lacks ensurepip). Supplementary full offscreen
  unittest discovery passed all 328 tests; log: `reports/relocation-unittest.txt`.
- Windows relocation subsequently passed: `reports/20261002T161141.558457Z`.
  The old sibling folder is gone. Safety/cleanup work still remains.

# Process containment slice — awaiting Windows run

- Replaced taskkill with a non-inheritable kill-on-close Job Object. Windows child
  scripts wait for a pipe token until assignment succeeds; assignment failures
  kill the gated child rather than run an uncontained scenario. If the runner
  exits before assignment, pipe EOF exits the child without starting descendants.
- Termination applies to the entire job even after the immediate child exits;
  query active process count until zero with a bounded deadline. Job handle closure
  also kills contained descendants if the runner exits unexpectedly.
- Added native timeout/descendant, abrupt-exit/descendant, handle-close, and
  assignment-refusal probes. Explicit Windows runner requires their success,
  stores separate logs, and hashes the helper and probe source. Linux reports
  native probes as not run, not passed.
- Review caught and fixed the gated launcher import-path difference from executing
  a script directly: prepend the script directory before runpy execution.
- Ruff check, formatting and diff whitespace check passed. Relocated Linux matrix
  passed: `reports/20261002T162206.454791Z`.
- Full offscreen unittest discovery passed 333 tests with four native Windows cases
  skipped: `reports/process-cleanup-unittest.txt`. Pytest remains unavailable.
- No native Windows cleanup claim yet; rerun the normal command on Windows.
  Changed/missing-file and sharing-lock/retry cases were subsequently implemented
  in the delivery below.

# Safety slice and two-axis review

Review baseline: checkpoint `f018981`, including the pending containment slice.
Parallel review agents are unavailable in this session; both axes were reviewed
locally, without claiming an independent sub-agent review.

## Standards

- Reviewed against AGENTS.md, tests/README.md and the code-review smell baseline.
  No unresolved standards findings. Shared source/target UI selection is extracted
  into one helper; no production code or unrelated legacy formatting changed.
- Focused mypy checks (Windows platform, follow-imports=skip, check-untyped-defs)
  found pipe-nullability, heterogeneous report inference and platform API issues;
  these were addressed. PyQt's QTest keyClick stub lacks staticmethod despite its
  runtime C++ namespace API; the single suppression is documented at the call.
- Ruff and format checks pass. Mypy passes for run.py, process_control.py,
  safety_cases.py, locked_copy.py and windows_lock.py.

## Spec

- Real generated JPEGs and real ExifTool at the approved public seams. Both backup
  settings cover changed/missing source/target refusal at preview and confirmation,
  with fresh unchanged-file positive controls. Final target-write guards are also
  exercised; independent file hashes/sets prove refusal did not write anything.
- Native Windows sharing handle allows reads while denying writes/deletion; a
  separate CreateFile write-open verifies ERROR_SHARING_VIOLATION. UI copy must
  produce one success/one failure, preserve originals/backups, and expose explicit
  retry. Releasing the handle and retrying must change only the failed target;
  successful/unselected file hashes and identities stay unchanged.
- Lock handles are released by a context manager even on assertion failure.
  Lock UI settings are isolated in a separate temporary sub-workspace. Every phase
  has a bounded child deadline and exact required case-result set. Linux explicitly
  reports native sharing locks/cleanup probes as not run.
- Normal-path and native cleanup Windows report verified:
  `reports/20261002T162912.910988Z`. New lock/retry cases still require Windows
  execution. Visual checks remain unrun; VISUAL_SMOKE.md records the minimal
  checklist and defers collapsible Scan setup to its separate UI ticket.
- No scope creep or unresolved portable implementation findings. Final Windows
  and visual acceptance are missing validation, not claimed success.

## Execution evidence

- First changed-source confirmation refusal passed:
  `reports/first-refusal.txt`. Production already rejected this case; no artificial
  production failure was introduced to manufacture a red-to-green claim.
- Full portable matrix: `reports/20261002T165651.503170Z`; 28 case results in
  ten phases, both temporary workspaces removed.
- Fresh optimization and missing-ExifTool guard runs failed explicitly with exit 1:
  `reports/safety-optimization-guard.txt`, `reports/safety-dependency-guard.txt`.
- Focused pytest: 15 passed, four Windows-only skips.
- Full offscreen pytest: 329 passed, four Windows-only skips;
  `reports/safety-full-pytest.txt`. Pytest/mypy were installed in `/tmp/tagger-dev-tools`
  for this refreshed container, without changing project dependencies.
- Summary: Standards — no unresolved findings; Spec — native lock/retry run and
  visual acceptance outstanding. M9 is not marked complete.
