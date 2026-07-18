# 03 — Handle Partial Batches and Selected Retry

Status: completed
Category: bug
Priority: high
Blocked by: 02

**What to build:**

For a tag mutation across multiple selected photos, TAGGER must communicate and retain per-photo outcomes. Successful photos become confirmed; failed photos restore Confirmed metadata and remain visibly failed. The `:retry` command must retry only failed mutations belonging to currently selected photos.

- [x] A multi-photo mutation can represent successful and failed photo writes in one user-visible outcome.
- [x] Successful photos remain confirmed while only failed photos are restored, marked failed, and eligible for retry.
- [x] The UI summarizes mixed batch results without hiding per-photo indicators.
- [x] `:retry` retries failed mutations for selected photos only and never resubmits successful or pending work.
- [x] Pure coordination and offscreen command-routing tests cover partial success and selected retry.

## Validation

- `ruff check --no-cache .`
- `python3 -m compileall -q actions.py exif_ui.py services tests`
- `QT_QPA_PLATFORM=offscreen python3 -m unittest discover -s tests -v` (41 passed)
- `git diff --check`
