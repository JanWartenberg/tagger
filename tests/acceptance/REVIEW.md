# Collapsed toggle placement — 02h follow-up

Per maintainer request, collapsing now moves the same Scan setup toggle directly
left of Add folder in the view header, centered at the same button height. The
entire setup frame is hidden; expanding returns the toggle to its section frame.
Focus is restored after reparenting. Alt+U remains tooltip-only.

Qt regressions verify ancestry, visibility, header position, equal height,
shortcut, reclaimed space and focus recovery. Full offscreen suite: **340 passed,
4 Windows skips, 33 subtests passed**. Ruff and diff checks pass. Native Windows
visual confirmation remains open; real-file suite was not rerun for this placement-only change.

# Scan setup frame and concise labels — 02h / 02i

Maintainer accepted button color and requested Alt+U only in the tooltip, with
the toggle integrated into the Scan setup frame. The frame now has a persistent
header and collapsible body; splitter sizing reclaims body space while preserving
an accessible expand control. Keyboard expansion, focus recovery and new-scan
expansion remain covered by public Qt tests.

Text review removed repeated copy guidance and header confirmation prose, moved
shortcut/detector explanations to tooltips, and shows shared time once per group.
Per-photo provenance, full paths, read failures, inspection-only restrictions and
explicit copy confirmation remain. No mutation/filter semantics changed.

Validation: Ruff and diff whitespace checks pass. Full offscreen suite: **340
passed, 4 Windows skips, 33 subtests passed**. Portable real-file runner passed:
`reports/20261003T150043.075948Z/report.json`. Windows placement/text-density review
and final M9 acceptance remain open.

# Scan setup toggle follow-up — 02h

Maintainer confirmed fixes 02e/02f/02g; their tickets are completed. Requested
subtler Scan setup toggle styling and a shortcut. Alt+U already existed; it now
appears on the button with explicit text-beside-arrow presentation. Neutral
palette-based fill replaces native checked-state accent fill; hover/focus remain
visible. Existing Edit mode remains for navigation/source/target/ignore keys;
removing it is an open product decision, not required for C.

New public-widget regression failed on the missing visible shortcut before the
fix and now passes, including rendered neutral fill and Alt+U operation. Full
offscreen suite: **339 passed, 4 Windows skips, 33 subtests passed**. Ruff passes.
Windows appearance confirmation of 02h and final M9 acceptance remain open.

# Latest UI blocker fixes — 02e / 02f / 02g

Maintainer supplied Windows evidence for clean 3a0f706: 32 cases passed,
lock/retry in both backup modes, native process cleanup and workspace removal.
Scan collapse and candidate filters work. Menu contrast failed; queue scrollbar
clipping and C requiring Edit mode were additionally reported. Ticket 01 remains
blocked pending Windows confirmation of these fixes.

Diagnosis/regression command (activated `/tmp/tagger-venv`, Linux):

```sh
PYTHONPATH=. QT_QPA_PLATFORM=offscreen pytest -q tests/test_main_window_characterization.py -k 'candidate_menu_does or queue_scrollbar or shortcut_works_without'
```

Before: three failures (wrong popup foreground; card bottom 89 > viewport 54;
Copy preview timeout). After: three passed. Fixes isolate popup styling from the
preview placeholder, allocate queue height from content plus scrollbar/frame,
and move C to Duplicate review scope while retaining typing/modifier guards.
Reviewed diff: no metadata/write behavior changes; preview still requires explicit
confirmation. Existing clicked-photo actions and modal navigation tests pass.

Validation: Ruff passes; full offscreen pytest rerun passes **338 tests and 33
subtests**, four Windows-only skips. A preceding full run segfaulted in a Qt
error callback during `test_copy_path_copies_every_selected_photo_path_as_plain_text`
with a metadata worker active. Unchanged rerun passed; cause not diagnosed or
claimed fixed. Portable real-file suite passed with cleanup:
`reports/20261003T142411.481142Z/report.json`.

Windows appearance/keyboard behavior and native regression of the fixes are not
yet confirmed. See VISUAL_SMOKE.md. No final acceptance or merge is implied.

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

# Outcome visibility regression

- Windows `reports/20261002T172205.633827Z` confirms current commit 92cc623 and
  passing cleanup, portable cases, and backup-off sharing-lock partial failure.
  Correct outcome labels existed, but the immediate visible-label assertion ran
  before Qt's layout/show events. Retry and backup-on phases were not reached.
- Minimized reproduction: real offscreen QWidget, add outcome labels and a retry
  button after showing the window, then invoke the unchanged assertion helper.
  Focused pytest fails with the same `AssertionError: []` before the fix:
  `reports/outcome-wait-red.txt`; passes after: `reports/outcome-wait-green.txt`.
- Fix: use the existing bounded event-loop wait for exact visible successful/failed
  labels and a visible enabled retry button. No arbitrary sleeps, no assertion
  weakening, no production change. One regression test remains in the normal suite;
  it skips only if PyQt6 is absent. No debug instrumentation left behind.
- Local checks: Ruff/format and focused Windows-platform mypy pass; portable matrix
  `reports/20261002T175123.833724Z` passes. Full offscreen pytest: 330 passed, four
  Windows-only skips; `reports/outcome-wait-full-pytest.txt`.
- Review against 92cc623: Standards — no unresolved findings; Spec — fix retains
  public-widget observation and bounded waits. Windows retry/backup-on validation
  and visual acceptance remain outstanding. Parallel review agents unavailable.
- Prevention: treat newly rendered Qt controls as asynchronous observable state,
  not immediately visible children. The shared wait helper is sufficient; no
  architectural change needed.

# Duplicate review usability follow-ups

## Confirmed Windows matrix

Reports `20261002T180831.153966Z` and `20261002T183244.546813Z` both identify
fa2be3f and pass twelve phases/32 results, native cleanup and both backup settings
for real lock/retry. Temporary workspaces were removed. These reports predate the
UI changes below; native UI regression and visual acceptance remain pending.

## Standards review — baseline fa2be3f

- Local two-axis review; parallel review agents unavailable. No unresolved scoped
  standards findings. No unrelated formatting: the baseline files already passed
  Ruff format; only modified/new files were formatted.
- Both file-pane and candidate views import one `photo_context_menu.py` builder.
  A typed callback record binds their different targets. Existing file-action
  services, prompts, status/error handling and containing-folder exclusion are
  shared, not copied. Candidate file actions never replace Workspace selection.
- Removed layout widgets are hidden before deferred deletion so rebuilding the
  queue/cards cannot leave old visible controls active. Tests select current
  visible controls with a bounded wait, rather than stale deleted-layout children.
- Ruff/format pass. Mypy passes for the menu builder and action registry. MainWindow
  has eight pre-existing mypy diagnostics; baseline/current comparison adds none.

## Spec review — 02b/02c/02d and maintainer request

- Explicit user-triggered Scan setup collapse (`Alt+U`, command/help entry), no
  automatic collapse or persisted preference. Scope/scan/results/source/target
  state remains intact; review receives the released space. Scope focus/new scan
  reopen controls; focus cannot remain in the hidden panel.
- Default queue requires a readable tagged source and a different readable empty
  target in scan evidence. Show all candidates (`Alt+A`) reveals dead ends, with
  inspection-only explanation/hint and no enabled copy. Existing non-empty filter
  applies only in all mode, is disabled otherwise and retains its selected value.
  Source/target choices and ignored/submitted outcomes survive filtering. Counts
  and empty-queue guidance reflect the effective mode. Write guards are unchanged.
- Candidate previews/cards request the same context menu via Qt events. Tests
  exercise Open/GIMP/copy/reveal for the clicked path, unchanged Workspace/review
  selection, error reporting, and shared folder exclusion. Tooltip explains that
  exclusion affects tagging, not the frozen duplicate scan.
- No unresolved portable implementation findings. New Windows visual behavior and
  real external app/menu integration are unverified; 02b/02c/02d stay needs-info.

## Tests and evidence

- Test-first failures recorded during execution: missing collapse toggle, dead-end
  groups visible by default, no candidate context menu, and misleading choose-target
  hint on inspection-only groups. All now pass through public Qt scan/control seams.
- Fixtures include the reported `FN, Eisvogel, Spektiv` / `Eisvogel` pair, wholly
  empty groups, unreadable source/target metadata, and actionable groups.
- Focused duplicate-review tests: 39 passed. Full offscreen pytest: 335 passed,
  four native Windows skips; `reports/review-usability-full-pytest.txt`.
- Portable real-file regression passed: `reports/20261002T191138.290129Z`.
- Next: same Windows runner command, then the updated VISUAL_SMOKE.md checklist.
  M9 and merge into main remain separate maintainer acceptance decisions.

# Maintainer visual acceptance — 2026-10-03

- Maintainer accepted collapsed Scan setup placement and Alt+U (02h), and said
  reduced labels are much better (02i). Both UI tickets are completed.
- Concise UI text is now the default in AGENTS.md: minimal persistent explanation,
  optional detail in tooltips/help, essential information visible.
- No separate expanded-placement visual confirmation, full smoke result or new
  Windows regression report was supplied. Latest Windows regression and remaining
  visual/native checks, including context-menu actions, remain open.
- This records UI acceptance. M9 remains open; changes remain uncommitted.

# Windows regression and further visual acceptance — 2026-10-03

- Verified `reports/20261003T213738.131220Z/report.json`: twelve phases and 32
  case results passed. Both backup modes, real sharing-lock partial failure/retry,
  native process cleanup and removal of both temporary workspaces passed.
- Environment: Windows-11-10.0.26300-SP0, Python 3.14.7, ExifTool 13.59, Qt 6.11.2,
  PyQt 6.11.0. Report records HEAD 3a0f706 and the uncommitted UI working tree.
- Maintainer confirmed expanded Scan setup placement, selection preservation and
  Alt+S/new-scan reopening. Native Open/GIMP/path-copy/reveal actions target the
  clicked photo; folder exclusion affects the tagging Workspace. 02d completed.
- Remaining visual checks: navigation/focus/help, source/target distinction, Copy
  preview/cancel, larger-font/display-scale readability and review/status areas.
  Automated report correctly leaves visual acceptance as not run; manual results
  are recorded separately here. M9 remains open; no commit or merge performed.

# Navigation, confirmation and compact results — 2026-10-03

## Maintainer findings and acceptance

Source/Target operation and earlier Copy preview functionality are confirmed.
Maintainer reported hjkl unavailable after Alt+U until pressing e, requested
source/target images and bold tags side by side, removal of redundant confirmation
prose, and a quieter replacement for the cramped Completed/group-id list.
Tracked in 02j/02k/02l; acceptance of the new presentation remains pending.

## Diagnosis and delivery

- Keyboard regression drives Alt+U, h/l/j/k without Edit mode and normal text-field
  typing. Initial fixture needed Show all to expose its second, empty-only group;
  the corrected test passes and an isolated runtime patch restoring the original
  modal group routes fails at group navigation. No production files were changed
  for that red verification (`/tmp/tagger-navigation-red.txt`).
- Cause: hjkl routes were restricted to Edit mode; the relocated toggle also
  lacked the review event filter. Routes now apply in both modes. Focus recovery
  captures the original focused control before relocation instead of attempting
  to focus the toggle before its parent changes. s/t/i retain Edit mode semantics.
- Dialog uses independently scrollable side-by-side source/target columns, bold
  plain-text canonical tags and confirmed-empty → copied target tags. Background
  image workers reuse the existing loader; callbacks guard closed/superseded dialogs.
  Full paths, backup setting, default Cancel and explicit y/n/Esc remain intact.
- Latest completed/ignored result has one flat summary; older results move to a
  menu. Pending/failed/cancelled results remain visible and reopenable. Earlier
  outcomes and ignored-group recovery remain accessible, with no technical group
  id in the persistent copy. Counts move to tooltips; lock/retry harness observes
  the same exact counts there. Result ordering follows review/completion.

## Review and evidence

- Scoped self-review: focus recovery, text input exclusions, help/README, literal
  labels, selected subsets, large target lists, asynchronous image lifetime,
  ignored-group restoration, partial failures and failed-only retry checked.
  No unresolved portable implementation findings. No delegated review used.
- Dialog/outcome tests failed before the requested presentation changes. Corrected
  Alt+U regression is red-capable against original modal routes and green now.
- Focused Qt run: 42 passed, two subtests passed. Full run initially found the old
  help expectation that hjkl requires Edit mode; updated to the intended behavior.
- Final Ruff/format and diff checks pass. Full offscreen pytest: 343 passed, four
  Windows skips, 33 subtests passed.
- Portable report `reports/20261003T220626.449205Z/report.json`: ten phases,
  28 cases, backups off/on passed; both workspaces removed. ExifTool 12.57.
  Native Windows lock/cleanup correctly reports not run.
- Offscreen dialog rendering inspected; real generated-image loading and source
  visibility while scrolling targets have a Qt regression. Windows visual
  confirmation and a new Windows matrix run are still required.
- Prevention: keyboard tests must cover the non-edit workflow after controls
  change parents; help must distinguish navigation from edit-only actions.
  No temporary production instrumentation remains. No commit or merge performed.

# Footer revision and Windows confirmation — 2026-10-03

- Maintainer accepted Alt+U navigation and improved confirmation. 02j/02k and
  the remaining focus acceptance in 02b are completed. Verified Windows report
  `reports/20261003T221813.709522Z/report.json`: twelve phases/32 cases, both
  backup modes, native lock/retry, process cleanup and workspace removal passed.
- Maintainer rejected the intermediate results widget, including its empty scroll
  area. Removed the widget, layout and scroll area entirely; no hidden legacy
  container remains. One auto-raised native footer button now shows a short Saved N
  status or aggregate pending/failed/cancelled attention.
- All group results remain in the footer menu with exact per-group counts and
  source identity; actions reopen outcomes, restore ignored groups and reach
  explicit failed-only retry. Status observer and Windows lock harness now use
  public QAction text/tooltip and trigger the result action. Metadata/hash/backup
  assertions are unchanged. Footer hides in tagging and resets on a new scan.
- Scoped self-review: removal, view switching, asynchronous outcomes, aggregate
  failure priority, retry/restoration, footer coexistence, reset and docs checked.
  No unresolved portable implementation findings. Offscreen footer image inspected.
- New regression failed before removal at the still-existing scroll-area assertion;
  it passes with footer-only results. Existing partial-failure/retry test checks
  visible 1 failed footer attention, then reopens the result through its action.
- Ruff/format and diff checks pass. Focused Qt run: 44 passed, two subtests.
  Full offscreen pytest: 344 passed, four Windows skips, 33 subtests passed.
- Portable `reports/20261003T222741.128862Z/report.json` verified: ten phases/
  28 cases, both backup modes, all phase cleanup and both workspace removals passed.
  Windows lock/process probes are correctly not run on Linux.
- Supplied Windows report predates the footer revision. New Windows regression
  and footer visual acceptance remain open under 02l. M9 remains open.
  No commit or merge performed.

# Checkpoint pre-commit review — 2026-10-03

Used the review-changes skill. Staged diff was empty; reviewed unstaged production
and test changes, plus the new candidate-queue module and tickets. No new
actionable findings. Latest unchanged implementation has Ruff/format passing and
full offscreen pytest: 344 passed, four Windows skips, 33 subtests passed; portable
real-file report `20261003T222741.128862Z` passed. Only documentation/status changed
for this checkpoint; the suite was not repeated without a new implementation change.
The requested commit records the current implementation and consistent handoff.
Windows/footer confirmation and remaining visual checks stay open. M9 remains
active; no push or merge requested. See BACKLOG.md for follow-session instructions.

# M9 closure — 2026-10-04

Maintainer reported Windows acceptance runner **PASSED** with
`tests/acceptance/reports/20261004T112405.399638Z/report.json`. The report
contents were not independently inspected in this session. Maintainer confirmed
navigation/focus/help, footer feedback and outcomes/retry/ignored restoration,
source/target retention across candidate filters, multi-target preview scrolling
and cancel return. Window scaling has no negative effects and is accepted.
Larger-font testing was not performed because the font is unchanged; this check
was explicitly waived and accepted, not recorded as passed.

All remaining M9 acceptance criteria are satisfied. No implementation or visual
acceptance remains; merge into main and push are separate decisions.

# Main integration — 2026-10-04

Maintainer authorized local integration if merge-risk checks found no blocker.
Documentation/acceptance commit `3e6b356` was reviewed; a stale remaining-work
section in the acceptance README was corrected before commit. Diff checks passed.

## Standards

Parallel code-review standards axis found no blocking documented violation.
Two non-blocking concerns remain: synchronous candidate-queue rendering performs
repeated linear group lookups and may scale poorly for large queues; mutable
assessment dictionaries and lifecycle logic are concentrated in MainWindow.
Neither is a demonstrated regression or a reason for speculative refactoring.
Performance work remains subject to the existing deferred ticket.

## Spec

Parallel code-review specification axis found no material missing or incorrectly
implemented requirement. Background scan/revalidation, final write guards,
failed-only retry, footer refinements and package entrypoints were checked.
Standards: zero blocking findings, two follow-up concerns. Spec: zero findings.

## Validation and integration

- Ruff passed; full offscreen pytest: 344 passed, four Windows-only skips.
- Inspected portable report `reports/20261004T122111.114146Z/report.json`:
  status passed, all ten phases passed. Native Windows checks are not run on Linux.
- The Windows result and visual acceptance recorded above remain valid; no
  production code changed after those confirmations.
- `main` was an ancestor of the accepted branch. Local fast-forward merge through
  `3e6b356` completed without conflicts; no push or branch deletion performed.
- This follow-up documentation commit records the final branch and review evidence.

# Real-workload performance follow-up — 2026-10-06

Added `perf/profile_real.py` using generated disposable Unicode-path JPEG copies
and production ExifTool, discovery, indexing, refresh, workspace and mutation
services. Reduced large-read subprocess starts with 1,000-photo adapter blocks;
refresh subgroups remain 200 and all writes remain unchanged.

- Passed: nine new subprocess-boundary tests, including error propagation and
  Unicode field/date identity. Four process-count cases failed before the change
  and passed afterward. Real 1,001-photo read/sync/refresh acceptance also passed.
- Passed: two independent three-repeat before/after comparisons. Final paired
  Linux/WSL medians: read 1.653→1.428 s (13.6% faster), initial index
  1.692→1.494 s (11.7% faster). Read/sync processes fell from five to one.
  Refresh remained five processes; no refresh improvement is claimed.
- Separate profiled runs: Python read peak rose by about 0.51 MiB; Python
  initial-index peak by about 0.38 MiB. Child memory not measured.
- Passed: Ruff check/changed-file format and full offscreen pytest: 364 passed,
  four Windows skips, 33 subtests.
- Passed and independently inspected: real-file regression report
  `reports/20261006T160518.906332Z/report.json`, ten phases, 28 cases, both backup
  settings, verified process cleanup. The unchanged matrix provides regression
  coverage; the new tests/harness validate the large-read change.
- At the portable checkpoint, unrun: native Windows timings (requested), cold-cache/camera-original timings,
  UI render latency, native Windows lock/cleanup rerun. No checks waived. Prior
  M9 native lock/cleanup and visual acceptance remain valid; process lifecycle,
  writes and UI were not changed. Linux measurements establish no Windows claim.
- Work remains uncommitted; subsequent Windows evidence and rollback follow.

## Inspected Windows performance evidence and rollback — 2026-10-06

Maintainer supplied both reports; the agent inspected JSON contents independently:
`perf/results/real-windows-200.json`, `perf/results/real-windows-1000.json`.
Windows 11 build 26300, Python 3.14.7 AMD64, ExifTool 13.59, same revision,
fixture hash/size and three repetitions. Both completed all assertion checks.

Bulk-read median improved 3.548→3.031 s (14.6%); initial-index median worsened
3.253→4.368 s (34.3%). Initial-index ExifTool median time improved
2.939→2.180 s, while other time increased. The unchanged sync (no ExifTool),
discovery, workspace and refresh controls also slowed substantially. First
bulk-read timings were outliers (14.384/21.942 s). These observations establish
timing drift, not its cause or a causal regression from read-block size.

The predeclared end-to-end criterion is unmet on Windows. Restored production
read blocks to 200; 1,000 remains only a benchmark override. The boundary tests
now cover both variants. No speedup is retained pending a reverse-order,
five-repeat Windows comparison. Native Windows execution was maintainer-run;
the reports were agent-inspected. Ticket remains needs-info, no commit.
Rollback verification passed: Ruff check/format and full offscreen pytest,
373 passed, four Windows skips, 33 subtests. Existing small-request real-file
regression coverage is unchanged by restoring the block size.

## Reverse-order Windows evidence and focused comparison

Independently inspected `perf/results/real-windows-repeat-1000.json` and
`real-windows-repeat-200.json`: five repetitions, reversed order, same
versions/revision/fixture hash. Read medians favor 1,000 by 18.3% and initial-index
medians by 30.3%, but unchanged-sync controls remain mismatched (0.089 versus
0.773 s) with large within-run swings. First bulk reads remain outliers.
The previous unfavorable initial-index result is therefore not resolved by
the new aggregate medians. Production default stays at 200, no commit.

Added focused `--compare-batches` mode: one fixture, full untimed metadata
warmup recorded separately, alternating order, fresh DB for each variant,
read/sync/unchanged-sync only, and raw/per-pair differences in the JSON.
Generated 201-photo/two-pair smoke passed both orderings and block boundaries.
The corresponding real-ExifTool pytest checks freshness, zero warm-sync reads,
both pair orders and complete indexing. Windows paired evidence remains unrun.

Local four-pair 1,000-photo report: `perf/results/real-linux-paired.json`.
Read medians 1.641→1.458 s; initial sync 1.728→1.493 s, with stable warm-sync
controls near 0.025 s. This is local evidence only, not Windows acceptance.
Median within-pair gains were 12.7% read and 13.4% initial sync.

Ruff/format and the new real-ExifTool harness integration test passed. The first
full run had 373 passes and one failure in the unchanged latest-selection preview
test (0.425 s versus its 0.4 s limit); a targeted rerun failed on an extra initial
preview start. The cause is undiagnosed; no preview code/test was altered here.
The unchanged full rerun passed: 374 tests, four Windows skips, 33 subtests in
116.33 s. Earlier failures are not presented as fixed or waived; no further
test repetitions were run after this full pass.

## Final Windows paired read-block acceptance — 2026-10-06

Maintainer ran and supplied `perf/results/real-windows-paired.json`; the agent
independently inspected all 36 samples, versions, fixture identity, balanced
order, warmup and subprocess counts. Windows 11/Python 3.14.7/ExifTool 13.59.
Median within-pair gains meet the predeclared 10% thresholds: 10.7% bulk read,
11.2% initial index. Five of six pairs improve each total; ExifTool time improves
in every pair (median 20.3%/21.2%). Control matching in the last two pairs
supports both orderings. All unfavorable samples remain in the report.

Retain 1,000-path adapter blocks. No further Windows performance run required.
Control timings still span about 0.09–1.05 s: these are noisy generated-fixture
results, not universal/camera-original/cold-cache improvement claims. Refresh
subgroups, writes, process lifecycle and UI remain unchanged. Native lock/cleanup
reruns and UI rendering timings remain unrun, not waived; prior acceptance is
preserved. Final local regression verification passed: Ruff/format, 374 pytest
cases, four Windows skips, 33 subtests. Independently inspected real-file report
`reports/20261006T164501.259170Z/report.json`: ten phases, 28 cases across both
backup settings and verified process cleanup. Ticket completed, no commit.
Earlier preview-test instability remains undiagnosed; this final run passed
without altering that test or preview code. No further repetitions requested.

## Pre-commit review — real-workload performance

Maintainer authorized review, fixes and commit. No blocker in production read
batching. Fixed benchmark-only findings: reject Python optimization before
fixtures/results, fail clearly on index-reset errors, and verify complete
post-write records, both exact keyword fields, readability and capture date.
Six additional focused regressions cover these cases. Focused tests (25) and
the broad three-photo read/index/refresh/write smoke passed. Ruff/format passed.
Current backlog handoff now states the final accepted behavior without obsolete
rollback/waiting-state bullets. No new Windows timing is needed: application
behavior is unchanged by these review fixes. Previous real-file report
`reports/20261006T164501.259170Z/report.json` remains the inspected regression
evidence for the application change. Full pre-commit pytest passed: 380 tests,
four Windows skips, 33 subtests in 41.62 s. Ruff/format and diff checks passed.
All actionable review findings are fixed; no unresolved commit blocker or
product question. The implementation, tests and acceptance notes are committed
together with maintainer authorization; no push.

# Configurable default index root — 2026-10-04

Implemented `:indexroot` with inspect/edit/browse, persisted preference, reset,
cancellation and visible validation/save errors. Existing marker discovery,
containment and empty-search root retention are preserved; saving leaves the
active workspace and last-folder preference intact.

- Passed: 11 focused pytest cases exercising Qt command/dialog controls, real
  isolated config persistence, new-window loading, invalid/removed roots and
  production path resolution. The focused suite was rerun after adding a guard
  against unexpectedly open test dialogs.
- Passed: `ruff check .`, changed-file Ruff format checks, and full offscreen
  pytest: 355 passed, four Windows skips, 33 subtests.
- Passed and independently inspected: portable real-file report
  `reports/20261004T174041.175361Z/report.json`, ten phases and 28 cases, both backup
  settings, with verified process cleanup. This is regression coverage;
  preference-specific acceptance comes from the focused tests.
- Initial runner attempts were blocked by restored workspace ownership and Git
  safe-directory checks before any photo phases. Corrected local permissions
  and supplied a process-local safe-directory setting; the complete run passed.
- Maintainer reported `:indexroot` opens the dialog and allows choosing a folder,
  accepted the change and authorized committing it. No independent desktop
  visual inspection was performed by the agent.
- Unrun: broader dialog scaling checks and native Windows automated execution.
  Windows sharing locks/native cleanup were unchanged and are not validated by
  this Linux run. Previous M9 acceptances remain valid; no new waiver.
  Implementation and updated acceptance notes are committed together.

# Persistent duplicate candidate ignores — 2026-10-07

Ticket 04 implements the agreed per-index persistence and evidence identity.
Decisions live in a separate `.tagger/ignored_candidates.sqlite`, preserving
ignores when the photo cache is rebuilt. Ignore advances only after successful
background persistence; errors leave the candidate visible and enter Session
errors. Tags and scan IDs do not affect identity. Changed members, timestamps
or provenance return candidates; historical records remain available for
inspection until explicitly restored or cleared.

Ignored candidates / `:ignoredcandidates` and ignored footer entries open a
read-only list with asynchronous photo previews, saved evidence and historical
tag labels. Restore and confirmed Clear all ignores are explicit, index-scoped
actions. Closing during loading discards stale widget updates. Footer copy
outcomes/retry behavior and prior unrelated M9 acceptance remain unchanged.

- Passed: Ruff check, changed-file format checks and diff whitespace checks.
- Passed: 11 focused persistence/Qt tests; final full offscreen pytest:
  **391 passed, four Windows-only skips**.
- Passed and independently inspected: final portable report
  `reports/20261007T175150.109036Z/report.json`, **fourteen phases/38 cases**,
  both backup settings, process cleanup and temporary-workspace removal.
  Ten added cases cover Ignore without photo writes, fresh-process persistence
  and read-only previews, explicit restore, confirmed clear-all, and changed
  capture provenance returning candidates. JPEG hashes and file sets remain
  unchanged by each application action.
- Preserved failed attempt: `reports/20261007T174722.360718Z` reached Ignore but
  asserted source visibility before Qt layout finished. Added bounded waits for
  visible source/Ignore controls. `reports/20261007T174904.450110Z` then passed
  all fourteen phases/38 cases, as did the final post-review run.
- Two independent read-only reviews in each of two rounds. Round 1 found
  filesystem path resolution during GUI-side identity hashing. The helper now
  performs lexical normalization on canonical scan paths, without filesystem
  access; its focused regression failed before and passed after the fix.
  Round 2 returned no findings; both reviewers independently ran 11 focused tests.
- Maintainer-reported: quick feature acceptance passed, followed by explicit
  commit authorization. Platform, detailed scaling observations and an automated
  report were not supplied. The accepted quick check should not be repeated.
- Unconfirmed, not waived: full Windows execution of this revision and detailed
  scaling coverage of the added dialog/header control. Inspect the supplied
  Windows report before closing ticket 04. Linux does not validate native
  sharing locks or Job Object cleanup. Existing unrelated acceptance stays valid.
- Implementation and acceptance notes are committed together with maintainer
  authorization. No merge or push requested.

## Windows persistent-ignore verification — 2026-10-07

Independently inspected maintainer-supplied, synced report
`reports/20261007T200507.473386Z/report.json`: Windows 11/Python 3.14.7/ExifTool
13.59, clean commit `1d6d909`. Every harness SHA-256 matched that committed revision.

- Passed: **sixteen phases/42 cases**, exact complete matrix for both backup
  settings. New ignore/reopen cases passed, including photo previews, read-only
  inspection, explicit restore, confirmed clear-all and changed capture evidence.
- Passed: native sharing-lock partial failure and failed-only retry in both modes;
  five native process-cleanup probes, independently inspected cleanup log.
- Verified: every phase exited zero and cleaned its process tree; both temporary
  workspaces were removed.
- Maintainer's prior quick acceptance remains accepted. The report explicitly
  records visual acceptance as not run; detailed scaling observations remain
  unreported, not claimed passed or waived. No repeat quick check requested.

Ticket 04 completed. Implementation remains committed as `1d6d909`; these
acceptance/status updates are uncommitted, with no new commit or push requested.

# Direct Duplicate review shortcuts — 2026-10-07

Ticket 05 removes Edit mode completely: no toggle button/state, `e` action,
`:duplicateedit` command or mode-specific help remains. Source `s`, target `t`,
Ignore `i` and Copy `c` work directly outside text inputs. Navigation and modifier
shortcuts are retained. Escape cancels an active scan, closes the command line/
dialogs or returns to Tagging. Copy still requires explicit preview confirmation.

- Passed: focused Duplicate review/help coverage, 41 tests and two subtests.
  The direct source regression failed before the change and passed afterward.
  Tests cover direct source/target/ignore, literal `scti` input with unchanged
  choices, recovery, removed mode UI/help and immediate Escape view return.
- Passed: full offscreen pytest, **392 tests/four Windows skips**, Ruff check,
  changed-file format checks and diff whitespace checks.
- Passed and independently inspected: portable real-file report
  `reports/20261007T210319.231900Z/report.json`, **fourteen phases/38 cases**,
  both backup settings, matching harness hashes, process cleanup and temporary
  workspace removal. Existing copy scenarios now choose source with `s`, exclude
  a target with `t` and open preview with `c`; Ignore scenarios press `i` on the
  selected candidate queue button. Hash/metadata/backup/refusal assertions remain.
- Maintainer confirmed ignoring and resetting work; preserve that acceptance.
  Previously inspected Windows report `20261007T200507.473386Z` validates the
  prior persistence revision, not the new keyboard harness. No repeat manual
  ignore/reset check or unrelated visual acceptance requested.
- Unrun: Windows execution of this shortcut revision. Request the existing
  automated runner and inspect its report; ticket 05 remains open for that step.
  Native lock/cleanup semantics are unchanged, with prior acceptance preserved.
- Code and documentation changes remain uncommitted; no commit requested.


# Ignored candidates shortcuts and header placement — 2026-10-07

The collapsed Scan setup toggle now sits immediately left of Ignored candidates.
View-scoped `Ctrl+I` opens the list, with tooltip/help coverage. Within the dialog,
`j/k` select, `r` restores the selected candidate, `a` opens confirmed clear-all,
and `c` closes; Escape remains available. Button labels have mnemonic underlines
and tooltips describe their shortcuts. Disabled/empty controls remain guarded.

- Passed: focused Qt coverage of placement, shortcut view scope, selection bounds,
  restore-one, declined/confirmed clear-all, empty list, labels/tooltips and close.
- Passed: full offscreen pytest, **395 tests/four Windows skips**, Ruff check and
  changed-file format checks.
- Failed initial harness attempt: `20261007T211948.031356Z` could not reopen with
  Ctrl+I after a modal close because offscreen Qt did not reactivate its parent.
  The harness now activates its own window and waits before sending the shortcut.
- Passed and independently inspected: `reports/20261007T212327.674774Z/report.json`,
  **fourteen phases/40 cases** with both backup settings. All phases exited zero,
  process cleanup was verified, both workspaces were removed and harness hashes
  match. Real-file cases use Ctrl+I, r/a/c and multi-record j/k navigation; photo
  hash/metadata safeguards remain covered.
- Unrun: updated Windows keyboard harness and native appearance of new controls.
  Prior Windows persistence/lock/cleanup and maintainer ignore/reset acceptance
  remain accepted. Ticket 05 awaits the updated Windows report.
- Changes remain uncommitted; no commit requested.


# Acceptance handoff — 2026-10-07

Maintainer plans the updated Windows acceptance run for **2026-10-08**. Ticket 05
is needs-info while awaiting that report; implementation and Linux verification
are complete. Windows checks remain unrun, not waived or passed. Inspect the
updated report against sixteen phases/44 cases and native cleanup coverage before
closing 05. Ticket 04 and prior ignore/reset acceptance remain completed/accepted.
No repeat manual check or commit requested; current changes remain uncommitted.


# Windows acceptance and visible-underlines fix — 2026-10-08

Maintainer supplied the checklist: **five PASS / one FAIL**, NOT READY. Placement,
Ctrl+I (opening a folder first is accepted), c/Esc close and tooltips passed.
AT-04 failed: Windows hides mnemonic underlines until Alt, then retains them.

Independently inspected `reports/20261008T161432.936635Z/report.json`: Windows 11,
Python 3.14.7, uncommitted implementation based on 1d6d909. All sixteen phases /
44 cases passed across both backup settings; all phase exits were zero, process
cleanup verified, temporary workspaces removed. Sharing-lock recovery and native
cleanup passed; harness hashes match current scripts. The report's visual status
is not run; visual results above are maintainer-reported checklist observations.

The fix applies a dialog-owned QProxyStyle to only Restore, Clear all ignores and
Close, requesting SH_UnderlineShortcut regardless of the platform's Alt state.
Focused regression simulates hidden platform mnemonics and failed before / passed
after the fix; all nine dialog tests pass. Full offscreen suite: **396 passed /
four Windows skips**; Ruff/format passed. Portable report
`20261008T161805.450253Z` independently inspected: fourteen phases/40 cases,
verified cleanup/workspace removal and matching harness hashes.

Only AT-04 requires a Windows visual recheck on a newly opened dialog before Alt.
Preserve AT-01/02/03/05/06 and prior ignore/reset acceptance. No full Windows runner
repeat requested for this appearance fix. Ticket 05 remains open; no commit requested.


# Ticket 05 acceptance completed — 2026-10-08

Maintainer confirmed “fixed” after the request to recheck AT-04 before pressing
Alt. Record immediate underline visibility as maintainer-reported PASS. Retain
AT-01/02/03/05/06: final checklist **six PASS / zero FAIL / zero NOT ASSESSED**,
**ACCEPT**. Ticket 05 completed; no remaining acceptance for this ticket.
Windows functional report and final Linux verification are recorded above.
Prior ignore/reset acceptance remains valid. Changes remain uncommitted; no
commit or push authorized.


# Windows full-suite output and command documentation — 2026-10-08

Maintainer supplied the full PowerShell transcript: setting QT_QPA_PLATFORM to
`offscreen` and running the project interpreter with `-m pytest` passed **all
400 tests in 56.34 seconds**, including Windows native probes. The supplied output
was inspected; this is a maintainer-run result, not agent execution on Windows.
Earlier Linux review runs failed the previously recorded preview-selection test
(also reproduced on committed HEAD); one run additionally segfaulted. Those Linux
failures remain unresolved and are not described as fixed by the Windows pass.

The supplied `python -m ruff check` output reports 34 findings under a rule set
broader than this repository's configuration. Its configuration source is not
known. README and tests/README now document PowerShell environment assignment,
`python -m pytest`, and explicit Ruff `--config pyproject.toml .` to make the
project check reproducible. The explicit-config Ruff check passed locally; the
corresponding Windows command remains unrun. No lint rules or Python implementation
were changed. Ticket 05 acceptance remains completed; changes are uncommitted.


# Ruff default-rule mismatch resolved — 2026-10-08

Windows settings confirmed the correct pyproject.toml was loaded but newer rules
were active. Ruff 0.16 expanded its defaults and removed E402; local Ruff 0.12
still used the earlier defaults. Installing Ruff 0.16 in an isolated temporary
location reproduced the exact 34 supplied findings with the unchanged config.
Source: https://astral.sh/blog/ruff-v0.16.0

Declared the project's existing rule set explicitly in `[tool.ruff.lint]`:
`select = ["E4", "E7", "E9", "F"]`. This preserves the established checks across
versions; no Python source changes or lint-rule expansion are included. Both
Ruff 0.12 and 0.16 passed `check --config pyproject.toml .` after the config change;
diff whitespace check passed. Windows rerun remains maintainer-run/unreported.
Earlier claims that explicit config selection alone resolved the mismatch were
incomplete: the implicit default rule set differed even with the same config.


# Second pending-change review and test-race fixes — 2026-10-08

Reviewed all pending source, harness, configuration, test and documentation changes,
including untracked ticket 05. There are no staged changes. No remaining actionable
findings after these fixes:

- Open-choice test: a fixed 10 ms timer could send A before the modal window owned
  focus, yielding Cancel. Triggering the callback immediately reproduced the exact
  failure. Making only the rejection timer immediate still passed; window-active
  waiting alone was insufficient. Activating/focusing the dialog and waiting for
  both QApplication.activeWindow and focusWindow corrected the early-key repro.
  The test now triggers immediately, waits for readiness, asserts the actual
  clicked button for A/O/C, and reports callback failures after dialog cleanup.
- Preview-selection test: the fixture's initial debounced photo-0 preview was
  still pending when the recording reader was installed. This reproduced the
  previously recorded extra-initial-load assertion failure. Finish that setup
  load before measuring rapid navigation. The last-photo-only and 0.4-second
  responsiveness assertions are retained.
- Documentation: removed the inaccurate claim that unittest discovery runs the
  complete pytest suite, clarified pytest/unittest coverage, and made historical
  report hash claims refer to the validated committed revision.

Passed: both corrected tests, then ten repetitions each (20 cases, zero failures
or errors); full offscreen pytest **396 passed/four Windows skips in 56.97s**.
Ruff 0.12 and 0.16 passed, changed Python format checks and diff whitespace passed.
The original Linux crash did not recur in this full run; its cause is not claimed
independently established. Production behavior was unchanged by these test fixes.

Maintainer confirmed the explicit-rule Ruff configuration passes on Windows.
Their earlier Windows suite passed 400 tests, followed by a run with 399 passes
and the open-choice timing failure. Windows verification of the two corrected
tests remains unrun locally; only that focused rerun is needed. Preserve ticket
05's accepted native appearance and independently inspected real-file matrix.
No repeat feature acceptance or real-file runner requested. Changes remain
uncommitted; no commit authorized.


# Final Windows regression confirmation — 2026-10-08

Maintainer supplied the final Windows 11/Python 3.14.7 console transcript:
`python -m pytest` passed **400 tests in 44.03 seconds**, including both corrected
tests and native process-cleanup coverage. Both `python -m ruff check --config
pyproject.toml .` and `python -m ruff check` passed. The supplied transcript was
inspected; these are maintainer-run Windows results, not agent execution.

This closes the pending Windows verification for the test-race fixes. Previous
feature acceptance and independently inspected Windows real-file evidence remain
valid. Review has no remaining actionable findings. Maintainer has no objections;
changes are ready to commit, but no explicit commit instruction has been given.
Changes remain uncommitted; no push authorized.


# Commit authorization — 2026-10-08

Maintainer explicitly requested commit after final Windows verification and the
second review. Implementation and final acceptance/status records are included
together. Ticket 05 is completed; no unresolved review or acceptance findings.
Earlier failure/reproduction notes remain historical evidence. No push requested.
