# Minimal Windows visual smoke

Direct shortcuts follow-up (2026-10-07): Edit mode control removed; source, target,
ignore and copy keys now act directly. No new manual check requested. Public Qt
tests and real-file keyboard scenarios validate observable behavior; previous
ignore/reset acceptance is preserved. Windows execution passed in independently inspected report
`20261008T161432.936635Z` (sixteen phases/44 cases plus native cleanup). Maintainer
accepted placement, Ctrl+I (after opening a folder), c/Esc close and tooltips.
AT-04 initially failed because underlines appeared only after Alt. A local
button-style fix requests them immediately; maintainer confirmed the fix on
2026-10-08. All six checklist checks are accepted; ticket 05 completed. The collapsed Scan
setup toggle now sits immediately left of Ignored candidates; matching height,
alignment and adjacency are automated. `Ctrl+I` opens the list and appears in its
tooltip/help. Ignored-list `j/k/r/a/c` and Escape are automated; Restore, Clear all
ignores and Close use mnemonic underlines and shortcut tooltips. Native placement,
tooltips and immediate underline visibility are maintainer-accepted. Previous
ignore/reset acceptance stays valid.

Persistent ignores follow-up (2026-10-07; previous unrelated checks remain valid):

Windows automated report `20261007T200507.473386Z` independently inspected:
sixteen phases/42 cases plus native sharing-lock and cleanup coverage passed on
`1d6d909`. Ticket 04 is completed with prior maintainer quick acceptance. The
report does not validate appearance; the detailed scaling item below remains
unreported rather than passed or waived.

- [x] Maintainer reported a successful quick feature acceptance check and
  authorized commit; later confirmed ignoring and resetting work. Detailed
  scaling observations were not supplied; do not repeat these accepted checks.
- [ ] Detailed scaling coverage (not reported by the quick check): Ignored
  candidates button and dialog fit at the usual Windows scaling.
  List, photo previews, long paths, capture evidence, historical tag labels and
  Restore / Clear all ignores / Close remain readable; keyboard focus is usable.
  Opening an ignored footer entry now inspects without restoring. Functional
  persistence/recovery is automated; this check concerns appearance only.

New dialog follow-up (2026-10-04; prior accepted checks below remain valid):

- [x] Maintainer confirmed `:indexroot` opens the dialog and allows choosing a
  folder, and accepted the change for commit. This is maintainer-reported evidence.
- [ ] Broader appearance check from both views: the path, Browse,
  Save, Cancel, Restore Defaults and validation errors fit at the usual scaling.
  Functional behavior is automated in `tests/test_default_index_root.py`.

Accepted by the maintainer on 2026-10-04. Larger-font testing was explicitly
waived because the font is unchanged; window scaling passed. Checked items
record accepted coverage, including that waiver. Metadata correctness, refusal,
partial failure and retry belong to `run.py`.

Launch from the repository root:

```powershell
.\.venv\Scripts\python tagger.py
```

Use disposable photo copies, not original photos. Open a same-capture-timestamp
candidate group with a tagged source and an empty target; do not confirm a write.

- [x] Photo Workspace ↔ Duplicate review navigation is visible and usable;
  keyboard focus and view-specific help match the active view. After Alt+U collapses
  setup, h/l navigates groups and j/k navigates photos without pressing e is
  already accepted (02j); do not repeat that check.
- [x] Scan setup toggle sits inside the section frame when expanded. Its original
  accepted collapsed position was directly left of Add folder. Ticket 05 now
  moves it immediately left of Ignored candidates, retaining height/alignment
  and no empty frame; automated Qt geometry tests pass for the new placement.
  Neutral color is accepted. Alt+U appears only in its tooltip.
  Collapse/expand with the toggle or Alt+U. Review gains
  space, scope/source/target choices survive, and Alt+S or a new scan reopens setup.
- [x] Candidate navigation remains readable at the usual window size; with at
  least seven candidates and horizontal overflow, the scrollbar does not clip
  card bottoms. Window scaling is accepted; larger-font testing was waived.
- [x] Default queue hides fully tagged/empty-only/unknown-only dead ends. Show all
  candidates reveals them for inspection; the non-empty filter is enabled only
  in all mode, retains its selection, and does not discard review choices.
- [x] Right-click a candidate image: Open, GIMP, Copy file path and Reveal use the
  clicked photo, not a different Workspace selection. Text/background contrast
  matches the readable tagging menu, from both the image and card. Entries match tagging;
  folder exclusion explicitly affects the tagging Workspace.
- [x] Source/target choices and excluded targets are visually distinguishable;
  controls work as expected (maintainer confirmed). Keyboard focus is checked
  separately under navigation above.
- [x] C opens Copy preview directly; typing c in a text field remains normal
  typing. Ticket 05 removes the former mode distinction. Preview clearly shows
  source and targets side by side, images and bold canonical tags, with target
  before/after tags and the backup setting. For multiple targets, source remains
  visible while targets scroll. Layout is accepted (02k). Multi-target visibility
  and cancel return were accepted on 2026-10-04. Cancel returns to a usable review
  without a write.
- [x] No results strip/scroll area between navigation and candidate cards. The
  footer shows a subtle Saved N or pending/failed/cancelled attention. Its menu
  reopens outcomes and reaches failed-only retry (02l). Its previously accepted
  immediate ignore restoration is superseded by explicit recovery in ticket 04.

Maintainer previously accepted Scan setup, candidate filtering, context menus,
scrollbar fixes, Copy shortcut, Alt+U navigation and the preview layout. On
2026-10-04, the remaining navigation/focus/help, footer actions, filter selection
retention, multi-target visibility and cancel return checks passed. Window scaling
has no negative effects and is accepted. Larger-font testing was not performed
and was explicitly waived.

Maintainer reported Windows runner PASSED:
`reports/20261004T112405.399638Z/report.json`. Report contents were not
independently inspected in this session; window-size details were not supplied.
M9 and tickets 02c/02l are completed. See `REVIEW.md` for the acceptance record.
