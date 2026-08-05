# 01 — Add Session Error History and `:errors`

Status: completed
Category: feature
Priority: low
Milestone: M2 — Reliable, scalable index operations
Blocked by: None

## Goal

Let users review timestamped tool errors from the current TAGGER session without interrupting normal non-modal feedback.

## Implementation Scope

- Record operational failures from discovery, index, search, filter, ExifTool, and file-action work, including failures already shown in a modal dialog.
- Record each failed tag mutation as one aggregate error, rather than one entry per photo.
- Do not record expected input-validation or workflow-state guidance, such as an unknown command, invalid query, or no selected photo.
- Keep at most 100 entries for the Application session; discard the oldest entry when adding a newer one beyond that bound.
- Each entry contains a local `HH:MM:SS` timestamp, a source label, and the user-facing error detail.
- Add `:errors` to the action catalogue. It opens a read-only dialog in reverse chronological order; when empty, it says `No errors in this session.`
- Do not add a clear command or persistence; a new Application session starts with an empty history.

## Acceptance Criteria

- [x] Qualifying operational failures are retained without replacing their existing footer or modal feedback.
- [x] Expected validation and workflow guidance does not create a Session error.
- [x] Tag-mutation failures create one aggregate Session error per failed mutation.
- [x] `:errors` appears in the command catalogue and presents entries newest first with timestamp, source, and detail.
- [x] The history retains at most 100 session-only entries and presents the agreed empty state.
- [x] Characterization tests cover qualification, cap/ordering, empty state, and command/dialog wiring.

## Comments

Created from `BACKLOG.md`; deliberately separate from the completed background discovery and index-I/O work.

Triage complete: the agreed Session error boundary and `:errors` interaction are ready for implementation.

Implemented and accepted. Targeted validation passed with `QT_QPA_PLATFORM=offscreen python3 -m unittest tests.test_error_history tests.test_main_window_characterization.MainWindowCharacterizationTests.test_errors_command_reports_an_empty_session tests.test_main_window_characterization.MainWindowCharacterizationTests.test_errors_command_records_filter_failures_but_not_unknown_commands tests.test_main_window_characterization.MainWindowCharacterizationTests.test_current_index_failure_uses_footer_feedback_without_a_modal tests.test_main_window_characterization.MainWindowCharacterizationTests.test_partial_batch_marks_only_failed_photo_and_retry_resubmits_only_it -v`, plus Ruff, `compileall`, and `git diff --check`.
