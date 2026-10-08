# 05 — Remove Duplicate review Edit mode

Status: completed
Category: feature
Priority: medium
Milestone: M-Future — Unscheduled opportunities
Blocked by: None

## Goal

Make Duplicate review keystrokes act directly without an Edit mode toggle.
Maintainer agreed this simplification and explicitly requested the change.

## Scope

- Direct `s` selects the focused eligible source, `t` toggles an eligible target,
  `i` remembers the selected candidate as ignored, and `c` opens copy confirmation.
- Retain `h/l` group and `j/k` photo navigation, scan/scope shortcuts and modifiers.
- Remove the mode button/state, `e` toggle, `:duplicateedit` and all current
  mode-specific help/tooltips. Historical delivery records remain historical.
- Keep text inputs typing normally and copy confirmation mandatory. Escape
  cancels an active scan, closes dialogs/the command line, or returns to Tagging.
- Preserve accepted ignore persistence/inspection/reset behavior. Maintainer
  explicitly confirmed ignoring and resetting work; do not repeat that manual check.

## Acceptance criteria

- [x] Source, target and ignore keys act without entering a mode.
- [x] Copy opens a preview directly and cannot write before confirmation.
- [x] Text input retains literal `scti` without changing review choices or writing.
- [x] No mode control/toggle/command remains; help lists direct keys.
- [x] Escape cancellation and return to Tagging are covered.
- [x] Real-file harness uses `s/t/c/i` through public Qt events, including Ignore
  from the selected candidate queue button, with photo/hash safeguards.

## Verification

- Failing-then-passing focused Qt regression: `s` initially did not select a
  source; with the mode removed, direct source/target/ignore and recovery pass.
- Focused Duplicate review/help coverage: 41 tests passed, two subtests.
- Passed: full offscreen pytest, 392 tests/four Windows-only skips; Ruff check,
  changed-file format and diff whitespace checks.
- Passed and independently inspected: portable real-file report
  `tests/acceptance/reports/20261007T210319.231900Z/report.json`, fourteen phases/
  38 cases across both backup settings; harness hashes, process cleanup and
  temporary-workspace removal verified. Source/target/copy/Ignore use direct keys.
- At this initial checkpoint, native Windows shortcut verification was unrun;
  it subsequently passed on 2026-10-08 (see Delivery state).
- No commit requested. Previous unrelated acceptance is preserved.

## Delivery state

Completed and accepted on 2026-10-08; maintainer authorized commit of the
implementation and acceptance records together. Windows functional report
`20261008T161432.936635Z` independently inspected: sixteen phases/44 cases and
native cleanup passed. Maintainer accepted AT-01/02/03/05/06, then confirmed the
AT-04 underline fix with “fixed”. Final checklist: six PASS / zero FAIL / zero
NOT ASSESSED; ACCEPT. The visual recheck is maintainer-reported evidence.

The final underline fix passed 396 offscreen pytest tests/four Windows skips,
Ruff/format and portable real-file report `20261008T161805.450253Z` (fourteen
phases/40 cases). Earlier ignore/reset acceptance remains valid. No commit or
push requested at that checkpoint; no remaining acceptance for this ticket.

## Header/shortcut follow-up

Maintainer additionally requested the collapsed Scan setup toggle immediately
left of Ignored candidates, and `Ctrl+I` for the list including its tooltip.

- Implemented: toggle inserts immediately before Ignored candidates with matching
  height/center alignment; expansion restores its original section header/focus.
- Implemented: view-scoped `Ctrl+I`, matching tooltip and generated help.
- Passed: failing-then-passing placement/shortcut tests, including a collapsed
  setup and shortcut inactivity in Tagging. Focused help/placement/shortcut: 3 passed.
- Real-file inspection now opens the list using `Ctrl+I`; persistence and
  read-only photo safeguards remain. Broad verification passed; see below.
- No commit requested; prior ignore/reset acceptance stays accepted.

## Ignored-list keyboard follow-up

Maintainer requested `j/k` for selection, `r` for selected restore, `a` for all
restore, and `c` for close with Escape retained. Recovery/close labels use
`&Restore`, `Clear &all ignores…`, `&Close` for mnemonic underlines and tooltips.

- Implemented: dialog-scoped shortcuts; selection is bounded, scrolls into view
  and does nothing while disabled/empty. Recovery uses the existing buttons,
  respecting their enabled state and clear-all confirmation.
- Passed: failing-then-passing Qt tests for multi-row navigation, selected restore,
  declined/confirmed all-restore, empty bounds, button mnemonics/tooltips and
  both close keys. Prior ignore/reset acceptance is preserved.
- Real-file cases now use `r/a/c`, plus a multi-record `j/k`/evidence/close case.
  The required matrix becomes 40 portable cases / 44 Windows cases.
- Ctrl+I's first real-file attempt (`20261007T211948.031356Z`) failed reopening
  after a modal close: offscreen Qt had no window manager to reactivate the
  parent for a WindowShortcut. The harness now activates its own window and
  waits for activation before sending Ctrl+I. Production shortcut scope is kept.
- Passed: full offscreen pytest, **395 tests/four Windows-only skips**, Ruff check
  and changed-file format checks.
- Passed and independently inspected: `20261007T212327.674774Z`, **fourteen
  phases/40 cases**, both backup settings, matching harness hashes, verified
  process cleanup and temporary workspace removal. Ctrl+I reopening, selected
  restore, confirmed all-restore, two-row navigation and close passed.
- Windows execution and native appearance were initially unrun; both are now
  accepted as recorded in Delivery state. Prior Windows persistence acceptance remains.
- No commit requested.


## Comments

2026-10-07 — Maintainer deferred Windows acceptance to tomorrow, 2026-10-08.
Linux verification is complete: 395 pytest passes/four Windows skips, Ruff/format
passed, and fourteen real-file phases/40 cases passed in
`20261007T212327.674774Z`. Ticket 04 stays completed. Await the updated Windows
report (expected sixteen phases/44 cases plus native cleanup checks), inspect it,
and update acceptance/status. Current changes remain uncommitted.


2026-10-08 — Created the standalone [Windows acceptance checklist](../../../../tmp/ticket-05-windows.html)
for the remaining runner and native placement/shortcut appearance checks. All six
checks start NOT ASSESSED; previous ignore/reset acceptance is excluded. Feedback
controls, summary generation and clipboard fallback were exercised in the browser
with mocked clipboard writes; actual system clipboard and Windows execution remain
unverified. Focused dialog regression rerun: eight tests passed. No implementation
files changed and no commit requested.


2026-10-08 — Maintainer supplied checklist results: AT-01 placement, AT-02 Ctrl+I,
AT-03 c/Esc close, AT-05 tooltips and AT-06 Windows matrix PASS. Opening a folder
before Ctrl+I is explicitly accepted. AT-04 FAIL: underlines appear only after Alt
and then remain visible. Windows report `20261008T161432.936635Z` independently
verified: sixteen phases/44 cases, both backups, all phase exit codes/cleanup,
sharing-lock coverage, native cleanup probes and workspace removal. Harness hashes
match current scripts. The report covers the implementation before the underline
fix; native appearance is assessed by the maintainer checklist, not the report.

Fix: a dialog-owned QProxyStyle forces SH_UnderlineShortcut for only the three
recovery/close buttons. Other controls retain platform behavior. A regression
simulating hidden platform mnemonics failed before the fix and passed afterward;
all nine focused dialog tests pass. Full verification passed: 396 pytest tests /
four Windows skips, Ruff/format, and portable report `20261008T161805.450253Z`
(fourteen phases/40 cases; cleanup and harness hashes independently inspected).
Remaining
acceptance: reopen the dialog on Windows before pressing Alt and confirm R / a / C
are visible immediately (AT-04 only). No commit requested.


2026-10-08 — Maintainer confirmed the underline fix with “fixed”, accepting the
remaining AT-04 Windows visual recheck. Preserve the other five PASS results.
Final decision ACCEPT: six PASS / zero FAIL / zero NOT ASSESSED. Ticket completed;
no further acceptance requested. Changes remain uncommitted; no commit authorized.


2026-10-08 — Second full pending-change review completed; no remaining actionable
findings. Stabilized open-choice focus readiness and preview fixture setup without
changing production behavior or weakening outcome/responsiveness assertions.
Twenty repeated cases passed; full Linux suite 396 passed/four Windows skips;
Ruff 0.12/0.16, formatting and diff checks passed. Maintainer confirmed Windows
Ruff passes after explicit rule selection. Windows confirmation of the two test
fixes remains pending; ticket's prior feature acceptance stays completed. See
`tests/acceptance/REVIEW.md` for failure/reproduction and verification evidence.
No commit requested.


2026-10-08 — Maintainer supplied final Windows full-suite results: 400 tests passed
in 44.03 seconds, including both stabilized tests; explicit-config and default
Ruff commands passed. This closes the pending test verification. Evidence is the
maintainer-supplied console transcript; prior independently inspected real-file
report and visual acceptance remain valid. No remaining acceptance or review
findings. Ready to commit on explicit instruction; currently uncommitted.


2026-10-08 — Maintainer explicitly requested the commit. Implementation, completed
ticket/status records, test-race fixes, lint configuration and verified acceptance
are included together in the authorized commit. No push requested.
