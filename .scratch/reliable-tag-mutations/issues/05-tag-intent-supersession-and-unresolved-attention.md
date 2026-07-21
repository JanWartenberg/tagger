# 05 — Tag-Intent Supersession and Unresolved Attention

Status: completed
Category: bug
Priority: medium
Blocked by: 01, 02, 03, 04

**What to build:**

Make the post-failure state of tag mutations precise without expanding TAGGER into a persistent sync or conflict-resolution system. Replace opaque pending-state transforms with explicit, per-tag add/remove intents so a later user intent can supersede only the failed intent it covers.

- [x] Model a tag mutation as explicit add/remove tag intents per photo, using case-insensitive tag identity.
- [x] When a later mutation for a photo addresses a tag identity covered by a failed mutation, remove only that failed intent from the retryable state; the later intent wins for that tag.
- [x] Preserve unrelated failed intents for the same photo. They remain visibly unresolved and are included by `:retry` and `:retryall` only while the photo belongs to the current Photo Workspace.
- [x] Preserve the existing fresh-read-and-replay behavior: a retry applies TAGGER's retained intent to the current file state, affects its addressed tags, and keeps unrelated external metadata changes.
- [x] Retain failed state for the running application session when its photo leaves the Photo Workspace. If the photo returns, render a small, non-alarming attention indicator distinct from the pending reload indicator.
- [x] The attention indicator gives normal retry guidance only. Do not retain or display technical error text for a returned photo.
- [x] Do not retry automatically and do not persist failed intents or indicators across a TAGGER restart.

## Implementation boundary

- Keep intent and retry-state ownership in the existing pending-tag-mutation seam; the Qt adapter maps user actions to intents and renders its resulting status.
- Do not add a durable mutation queue, conflict dialog, retry policy, new tagging workflow, or a general MainWindow refactor in this ticket.
- Keep `:retry` scoped to selected photos and `:retryall` scoped to the current Photo Workspace.

## Testing

- Add pure coordinator coverage for multi-tag partial supersession: a later intent for `A` removes only a failed intent for `A`, while a failed intent for `B` remains retryable.
- Cover case-insensitive tag identity and both later add and later remove intents.
- Cover a failed photo leaving and returning to a Photo Workspace during the same application session; its attention state returns and remains scoped out of retry commands while absent.
- Cover that a new coordinator after a simulated application restart has no failed state.
- Update offscreen adapter coverage to distinguish the pending reload indicator from the non-alarming unresolved-attention indicator and to assert its normal retry guidance.
- Preserve the existing external-metadata replay, selected retry, retry-all, partial result, and workspace-transition tests.

## Validation

- `ruff check --no-cache .`
- `ruff format --check --no-cache exif_ui.py services/pending_tag_mutation.py services/tag_mutation.py tests/test_pending_tag_mutations.py tests/test_main_window_characterization.py`
- `python3 -m compileall -q exif_ui.py services tests`
- `QT_QPA_PLATFORM=offscreen python3 -m unittest discover -s tests -v`
- `git diff --check`

Completed validation:

- `ruff check --no-cache .`
- `ruff format --check --no-cache exif_ui.py services/pending_tag_mutation.py tests/test_pending_tag_mutations.py tests/test_main_window_characterization.py`
- `python3 -m compileall -q exif_ui.py services tests`
- `QT_QPA_PLATFORM=offscreen python3 -m unittest discover -s tests -v` (74 tests)
- `git diff --check`
