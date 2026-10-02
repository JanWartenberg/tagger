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
- [ ] Scan setup and candidate navigation remain readable at the usual window
  size; labels, buttons and photo previews are not clipped or illegible.
- [ ] Source/target choices and excluded targets are visually distinguishable;
  keyboard focus is apparent and controls do not require guessing hidden commands.
- [ ] Copy preview clearly shows the source, selected targets, canonical tags and
  backup setting. Cancel returns to a usable review without a write.
- [ ] Review/status areas are readable and their navigation is understandable.

Collapsible Scan setup remains a separate UI follow-up in
`.scratch/duplicate-photo-detection-and-tag-propagation/issues/02b-collapse-scan-setup.md`.
Check its layout/focus after implementation; do not claim it passed now.
Record Windows version, commit, window size and any findings in `REVIEW.md`.
