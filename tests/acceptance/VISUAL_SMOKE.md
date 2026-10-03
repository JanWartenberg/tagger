# Minimal Windows visual smoke

Not automated; partially accepted by the maintainer. Remaining items are open. Metadata correctness, refusal, partial failure
and retry belong to `run.py`; do not repeat their terminal choreography manually.

Launch from the repository root:

```powershell
.\.venv\Scripts\python tagger.py
```

Use disposable photo copies, not original photos. Open a same-capture-timestamp
candidate group with a tagged source and an empty target; do not confirm a write.

- [ ] Photo Workspace ↔ Duplicate review navigation is visible and usable;
  keyboard focus and view-specific help match the active view. After Alt+U collapses
  setup, h/l navigates groups and j/k navigates photos without pressing e is
  already accepted (02j); do not repeat that check.
- [x] Scan setup toggle sits inside the section frame when expanded. Collapsed,
  it sits directly left of Add folder at the same height, with no empty frame.
  Neutral color is accepted. Alt+U appears only in its tooltip.
  Collapse/expand with the toggle or Alt+U. Review gains
  space, scope/source/target choices survive, and Alt+S or a new scan reopens setup.
- [ ] Candidate navigation remains readable at the usual window size; with at
  least seven candidates and horizontal overflow, the scrollbar does not clip
  card bottoms. Also check a larger font/display scale.
- [ ] Default queue hides fully tagged/empty-only/unknown-only dead ends. Show all
  candidates reveals them for inspection; the non-empty filter is enabled only
  in all mode, retains its selection, and does not discard review choices.
- [x] Right-click a candidate image: Open, GIMP, Copy file path and Reveal use the
  clicked photo, not a different Workspace selection. Text/background contrast
  matches the readable tagging menu, from both the image and card. Entries match tagging;
  folder exclusion explicitly affects the tagging Workspace.
- [x] Source/target choices and excluded targets are visually distinguishable;
  controls work as expected (maintainer confirmed). Keyboard focus is checked
  separately under navigation above.
- [ ] C opens Copy preview without entering Edit mode (and still works in Edit
  mode); typing c in a text field remains normal typing. Preview clearly shows
  source and targets side by side, images and bold canonical tags, with target
  before/after tags and the backup setting. For multiple targets, source remains
  visible while targets scroll. Layout is accepted (02k). This composite item
  remains open only for manual multi-target visibility and cancel return. Cancel returns to
  a usable review without a write.
- [ ] No results strip/scroll area between navigation and candidate cards. The
  footer shows a subtle Saved N or pending/failed/cancelled attention. Its menu
  reopens outcomes, restores ignored candidates and reaches failed-only retry (02l).

Maintainer confirmed Scan setup collapse and candidate filters work on 3a0f706.
Menu contrast failed; queue clipping and modal Copy were additionally reported.
Maintainer subsequently confirmed fixes 02e/02f/02g. On 2026-10-03, the maintainer
accepted collapsed Scan setup placement, Alt+U and concise labels (02h/02i).
Maintainer subsequently accepted expanded placement, preserved selection and
Alt+S/new-scan reopening, plus native context-menu actions and folder exclusion.
Windows regression report `reports/20261003T213738.131220Z/report.json` was verified:
twelve phases/32 cases, both backup modes and native cleanup/lock retry passed.
Report platform: Windows-11-10.0.26300-SP0. Window-size details were not supplied.
Unchecked composite items retain checks not separately confirmed; earlier filter,
scrollbar and Copy-shortcut acceptance remains valid.
Maintainer accepted Alt+U navigation (02j) and improved confirmation (02k).
Windows report `reports/20261003T221813.709522Z/report.json` was verified: twelve
phases/32 cases, both backup modes, native cleanup and lock/retry passed.
Footer revision 02l still awaits Windows regression/visual confirmation; that
report predates the removal of the in-page results widget. Tickets live in
`.scratch/duplicate-photo-detection-and-tag-propagation/issues/`.
Record Windows version, commit, window size and any findings in `REVIEW.md`.
