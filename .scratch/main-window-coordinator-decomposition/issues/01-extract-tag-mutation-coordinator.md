# 01 — Extract the Tag Mutation Coordinator

Status: completed
Category: refactor
Priority: high
Blocked by: None

## Goal

Move tag-mutation queueing and lifecycle rules from MainWindow into one Qt-free Tag Mutation Coordinator while preserving reliable tag-mutation behavior.

## Acceptance Criteria

- [x] The coordinator owns serialized mutation execution, pending/failed lifecycle transitions, workspace-generation stale-work rejection, and removal of queued mutations for photos that depart the Photo Workspace.
- [x] The coordinator composes the existing confirmed-state and tag-intent rules and publishes immutable lifecycle facts sufficient for MainWindow to render pending/failed state and submit confirmed metadata to the index.
- [x] MainWindow no longer owns a tag-mutation queue, in-flight flag, or mutation-completion stale-work decision.
- [x] MainWindow retains widget rendering, metadata-cache updates, index submission, footer wording, focus, and scroll behavior.
- [x] `:retry` and `:retryall`, partial outcomes, external-metadata replay, and returned-photo unresolved attention retain their current behavior.
- [x] Replacing the Photo Workspace discards queued work for departed photos; in-flight completions retain file/index correctness but cannot render into the replacement workspace.

## Scope

- Add one Qt-free coordinator module beside the existing mutation services.
- Accept the mutation executor and background runner at its seam; production adapts the existing worker/thread-pool mechanism and direct tests use deterministic fakes.
- Migrate MainWindow incrementally to forward mutation intent and render coordinator lifecycle facts.

## Out of Scope

- Input/key routing extraction.
- Selected-photo metadata loading or preview lifecycle extraction.
- Changing tag-mutation user behavior, metadata formats, retry scope, or index semantics.

## Tests

- Add direct coordinator tests for ordering, success, failure, partial outcomes, retries, departure discard, and stale in-flight completion.
- Preserve or adapt offscreen MainWindow coverage for pending/failed indicators, retry commands, index submission, and workspace replacement.

## Validation

- `ruff check --no-cache exif_ui.py services/tag_mutation.py services/pending_tag_mutation.py services/tag_mutation_coordinator.py tests/test_pending_tag_mutations.py tests/test_main_window_characterization.py`
- `ruff format --check --no-cache exif_ui.py services/tag_mutation.py services/pending_tag_mutation.py services/tag_mutation_coordinator.py tests/test_pending_tag_mutations.py tests/test_main_window_characterization.py`
- `QT_QPA_PLATFORM=offscreen python3 -m unittest discover -s tests -v`
- `git diff --check`

## Comments

- Implemented with direct deterministic coordinator tests and the complete offscreen suite passing (86 tests).
