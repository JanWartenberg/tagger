# Minimal Windows visual smoke

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
- [x] Scan setup toggle sits inside the section frame when expanded. Collapsed,
  it sits directly left of Add folder at the same height, with no empty frame.
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
- [x] C opens Copy preview without entering Edit mode (and still works in Edit
  mode); typing c in a text field remains normal typing. Preview clearly shows
  source and targets side by side, images and bold canonical tags, with target
  before/after tags and the backup setting. For multiple targets, source remains
  visible while targets scroll. Layout is accepted (02k). Multi-target visibility
  and cancel return were accepted on 2026-10-04. Cancel returns to a usable review
  without a write.
- [x] No results strip/scroll area between navigation and candidate cards. The
  footer shows a subtle Saved N or pending/failed/cancelled attention. Its menu
  reopens outcomes, restores ignored candidates and reaches failed-only retry (02l).

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
