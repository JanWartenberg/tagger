# Minimal Windows visual smoke

Not automated and not yet passed. Metadata correctness, refusal, partial failure
and retry belong to `run.py`; do not repeat their terminal choreography manually.

Launch from the repository root:

```powershell
.\.venv\Scripts\python tagger.py
```

Use disposable photo copies, not original photos. Open a same-capture-timestamp
candidate group with a tagged source and an empty target; do not confirm a write.

- [ ] Photo Workspace ↔ Duplicate review navigation is visible and usable;
  keyboard focus and view-specific help match the active view.
- [ ] Collapse/expand Scan setup with its header toggle or Alt+U. Review gains
  space, scope/source/target choices survive, and Alt+S or a new scan reopens setup.
- [ ] Candidate navigation remains readable at the usual window size; labels,
  buttons and photo previews are not clipped or illegible.
- [ ] Default queue hides fully tagged/empty-only/unknown-only dead ends. Show all
  candidates reveals them for inspection; the non-empty filter is enabled only
  in all mode, retains its selection, and does not discard review choices.
- [ ] Right-click a candidate image: Open, GIMP, Copy file path and Reveal use the
  clicked photo, not a different Workspace selection. Menu entries match tagging;
  folder exclusion explicitly affects the tagging Workspace.
- [ ] Source/target choices and excluded targets are visually distinguishable;
  keyboard focus is apparent and controls do not require guessing hidden commands.
- [ ] Copy preview clearly shows the source, selected targets, canonical tags and
  backup setting. Cancel returns to a usable review without a write.
- [ ] Review/status areas are readable and their navigation is understandable.

Scan setup, candidate-filter and context-menu follow-ups are implemented but their
Windows visual acceptance is not yet passed. Tickets: `02b`, `02c`, and `02d` in
`.scratch/duplicate-photo-detection-and-tag-propagation/issues/`.
Record Windows version, commit, window size and any findings in `REVIEW.md`.
