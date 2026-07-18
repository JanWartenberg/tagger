# 02 — Preserve Pending Mutation Sequences

Status: completed
Category: bug
Priority: high
Blocked by: 01

**What to build:**

When a user makes multiple tag changes to the same photo before earlier writes finish, TAGGER must preserve later Pending tag mutations if an earlier one fails. Before writing a pending mutation or retrying one, TAGGER must obtain current file metadata and replay the original user intent, preserving unrelated metadata changes made outside TAGGER.

- [x] A later requested mutation remains pending after an earlier mutation for the same photo fails.
- [x] Later pending intent is recomputed from Confirmed metadata rather than discarded or overwritten by rollback.
- [x] Execution replays the user's logical tag intent against freshly read file metadata; the retained logical transform is available for Ticket 03's retry command.
- [x] Unrelated externally added metadata survives the replayed user intent.
- [x] Tests cover an earlier failure followed by a later pending mutation and an external metadata change before the later execution.

## Validation

- `ruff check --no-cache .`
- `ruff format --check --no-cache exif_ui.py services/pending_tag_mutation.py tests/test_pending_tag_mutations.py tests/test_main_window_characterization.py`
- `python3 -m compileall -q exif_ui.py services/pending_tag_mutation.py tests`
- `QT_QPA_PLATFORM=offscreen python3 -m unittest discover -s tests -v` (36 passed)
- `git diff --check`
