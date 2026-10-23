# 06 — Investigate intermittent Qt preview-navigation crash

Status: ready-for-agent
Category: bug
Priority: medium
Blocked by: None

## Problem and scope

`tests/acceptance/REVIEW.md` records a Linux full-suite segfault in
`test_duplicate_copy_navigation_invalidates_a_background_preview` during scroll
commit isolation on 2026-10-18. The isolated test and a subsequent full suite
passed. Parallel acceptance was a recorded circumstance, not an established cause.
Earlier records describe other Qt crashes without preserved diagnostic stacks.

Reproduce the navigation crash before changing worker, signal or image lifetime
handling. A passing rerun is not evidence that the crash is fixed. Keep metadata
mutation services and CI/acceptance harness wiring outside this investigation.

## Investigation — 2026-10-21

Work was isolated in the app-managed `investigate/qt-preview-crash` worktree,
starting at `1b530958a0c37051b3c04676d01d185f741c19eb`. The initial investigation
used unchanged repository code; the subsequent test-lifetime correction is
described below. Production code and the acceptance/CI harness are unchanged.

Environment: Linux/WSL2, Python 3.11.2, PyQt6 6.11.0, Qt runtime 6.11.2,
pytest 9.1.1, Ruff 0.17.1, ExifTool 12.57. The reused development interpreter is
`/tmp/tagger-refresh-venv/bin/python`. Historical acceptance reports show both
Qt 6.4.2 and 6.11.2 under the same older interpreter path, so that path cannot
establish the crashing process's dependency versions.

### Reproduction attempts

The reproduction drivers enable Python faulthandler, capture separate child
stdout/stderr, and bound execution with process-group cleanup. The real-file
acceptance runner separately verifies its descendant cleanup. Disposable fixtures use
fake metadata/index adapters and generated JPEGs, never personal photos.
Scripts, version snapshots, child exit codes and logs are preserved in
`/tmp/tagger-qt-crash-20261021/`.

- Original targeted test: **100 fresh processes passed**. Each starts a new
  QApplication and runs the unchanged test.
- Suite accumulation: **1,000 repetitions passed** within one QApplication,
  with fixture cleanup results explicitly asserted.
- Late-completion probes: **five fresh processes × 180 cases passed**. Events
  hold metadata or real QImageReader work across navigation, leaving review,
  dialog cancellation and window close. Both successful JPEG decoding and missing
  images are covered. Old dialog/card deletion is asserted before releasing
  reads; callbacks must drain worker tracking sets; gate timeouts fail the probe.
  Window close in these probes means closing/hiding a retained window.
- Object collection: **300 repetitions passed**, adding `gc.collect()` immediately
  after the original test's group navigation, with the QApplication still alive.
- Full current suite: **26 fresh processes passed**, each reporting **424 passed,
  four Windows skips, 33 subtests passed**: three baseline runs, twenty additional
  runs and three with parallel real-file acceptance.
- All three deliberate parallel acceptance runs passed **18 phases / 48 cases**
  each. Independently inspected child exits, cleanup, six removed workspaces and
  matching harness hashes. Reports:
  `20261021T191447.138332Z`, `20261021T191543.892470Z`,
  `20261021T191640.866908Z` under `tests/acceptance/reports/`.

These counts describe the initial unchanged baseline. Independent review
confirmed them against logs and JSON records.

The unchanged targeted command is:

```sh
QT_QPA_PLATFORM=offscreen /tmp/tagger-refresh-venv/bin/python -X faulthandler -m pytest -q tests/test_main_window_characterization.py::MainWindowCharacterizationTests::test_duplicate_copy_navigation_invalidates_a_background_preview
```

Temporary probe commands (run from this worktree):

```sh
/tmp/tagger-refresh-venv/bin/python /tmp/tagger-qt-crash-20261021/repeat.py lifecycle-timeout-checked 5 /tmp/tagger-qt-crash-20261021/test_stress.py
```

```sh
/tmp/tagger-refresh-venv/bin/python /tmp/tagger-qt-crash-20261021/repeat.py accumulated-verified 1 /tmp/tagger-qt-crash-20261021/test_repeated.py
```

### Separate observations and probe corrections

A temporary process-exit probe produced **SIGABRT**, with
`Worker.run()` emitting `finished` after its `WorkerSignals` C++ object had been
deleted. The first batch failed at iteration 16; a further 100 processes failed
twice (iterations 19 and 45). These failures occurred after the Qt event loop
ended, not during the original navigation test. The probe retains global test
fixtures and differs from the function-local launcher lifetime. Two reduced
probes, with global and function-local QApplication ownership, each passed 100
processes. Thus no minimized production shutdown reproduction or causal link to
the navigation segfault is established. No shutdown fix is included.

The process-exit probe's first JSON field `work_finished_after_event_loop`
overstated its observation: its event proves a held metadata read returned, not
that the outer Worker finished. The corrected script names that observation
`held_read_returned_after_event_loop`.

Independent probe review caught swallowed unittest cleanup failures, missing
deletion/callback assertions and gate timeouts consumed by normal worker error
handling. The final 900-case result above uses corrected assertions. Earlier
exploratory batches are retained but are not substituted for this result.

A temporary driver named `concurrent.py` shadowed Python's standard module and
unintentionally launched nested test/acceptance processes. The affected batch was
discarded, the driver renamed, its owned process tree stopped and its generated
workspace removed. Cleanup records are in the temporary evidence directory.
The three subsequent deliberate parallel runs use the renamed driver.

## Reproduced test-lifetime defect — 2026-10-22

Removing the three later folder-refresh test modules restores the earlier
**399 passed / four skips / 33 subtests** scope. Ten fresh runs passed. Adding
only an autouse `gc.collect()` after each test then produced an in-suite
**SIGSEGV** on the third run, in
`test_duplicate_copy_shortcut_opens_confirmation_directly` while searching for
the copy dialog. The first two collection-stress runs passed; the remaining two
planned runs were not executed after the failure.

Reduction retained nine ignored-candidate UI tests before thirteen duplicate-copy
tests: **22 cases per fresh process**. Native crashes occurred in several copy
dialog waits, rather than only one navigation assertion. Twenty repetitions of
the thirteen copy tests alone passed. Further two-test reductions also passed;
they do not invalidate the larger reproducer's failures.

GDB was downloaded from Debian packages and extracted only under the temporary
diagnostic directory; no system package or project dependency was changed.
Native captures include:

- `native-prefix-008.log`: `QObject::objectName()` called from recursive
  `qtcore_do_find_child`; pooled threads were waiting in this snapshot.
- `native-pointer-001.log`: the same path with an invalid QObject private-data
  pointer (`0x31`). This is evidence of invalid object state, not identification
  of which lifetime transition corrupted it.
- `native-child-003.log`: a different failure during `QObject::connect` /
  `PyQtSlotProxy` construction. A search-only workaround would miss this case.

### Controlled comparison and correction

The same 22-case collection-stress prefix completed **30 baseline processes**:
**five SIGSEGVs / 25 passes** (`prefix-rate-control-results.json`). Retaining one
QApplication for the whole process, with no production changes, completed
**30 processes / zero failures** (`prefix-retained-app-results.json`).

A fresh-process regression then exercised the real ignored-candidate and default
index-root fixtures. Before the fix it deterministically failed with
`QApplication destroyed between UI fixtures` after the first fixture's cleanup.
It uses a weak reference, so the assertion does not itself retain the application.
The pre-fix log is `lifetime-regression-red.log`.

The correction is confined to tests: `qt_test_application.application()` lazily
retains one QApplication until process exit. All three existing GUI-application
creation sites now use it. Core-only tests do not import this helper or create
Qt state. The regression checks application survival after actual fixture
cleanup and reuse across both fixtures and the characterization test class.
It passed after the correction. The earlier inter-fixture application destruction
is therefore a demonstrated defect, independently of crash frequency.

With the actual shared helper (without the diagnostic retention plugin), the
previously crashing 22-case prefix passed **100 fresh processes / zero failures**
under the same inter-test collection stress (`prefix-fixed-results.json`).

Independent review found no blocking issues in the helper, its three callers,
the regression or documentation. Final verification:

- Ruff lint and all five affected Python files' format checks passed.
- Full Linux offscreen suite: **425 passed, four Windows skips, 33 subtests**.
- Five full historical-scope collection-stress runs: **400 passed, four Windows
  skips, 33 subtests each**, including the new lifetime regression.
- Post-fix real-file acceptance: **18 phases / 48 cases** in
  `tests/acceptance/reports/20261022T165709.815353Z/report.json`. All child exits,
  process-tree cleanup, removed workspaces and harness hashes were inspected.
- `/tmp/tagger-qt-crash-20261021/fix-verification.json` records verified results,
  the report hash and hashes of the five tested Python files.

### Scope of the conclusion

The demonstrated **test QApplication lifetime defect** is corrected. The native
collection-stress failures occurred in the same duplicate-copy workflow but
different tests from the originally recorded navigation crash. The historical
navigation stack and exact environment remain unavailable, so this is not proof
that every historical Qt crash shared this cause. The separate shutdown-probe
abort remains outside this fix.

## Remaining work

The exact original navigation segfault remains unreproduced. Do not infer a
production worker defect from the historical record, or conflate it with the
separate shutdown probe and unrelated Qt aborts. This issue remains open for the
historical failure rather than marking that unobserved case fixed.

Continue with a bounded comparison of exact Qt dependencies and suite order when
the original crashing environment or another navigation stack is available. Keep
faulthandler logs and dependency versions with every failure. A native debugger
backtrace from an in-suite navigation crash would distinguish it from shutdown
and unrelated style-test failures.

The maintainer reports that Windows acceptance is running. Its result and report
are pending and have not been independently inspected; Windows pytest remains
unrun in this investigation. No visual behavior changed and no previous visual
acceptance was invalidated.

The maintainer authorized committing the reviewed test fix while Windows
acceptance is running, and later authorized merging into local `main`. No push
was requested. Integration with `badde1c` passed Ruff, 476 tests (four Windows
skips, 33 subtests), and real-file acceptance (18 phases / 50 cases) on
2026-10-23. The inspected report is
`tests/acceptance/reports/20261023T221828.235014Z/report.json`; see REVIEW.md for
its hash and verification details. Windows results remain pending. The
historical-crash issue remains open as described above.
