# Backlog

## Product work

### Empty-filter SQLite check with background file-scan crosscheck (medium priority)

- Show the SQLite-derived IPTC-empty result immediately, then crosscheck it with a full background file-metadata scan.
- Keep the initially displayed filter view stable; the crosscheck must never change it automatically.
- When the crosscheck finds a discrepancy, repair the index, report the difference in the status bar, and offer `:resync`.
- `:resync` applies the already-completed crosscheck result atomically and immediately; it does not start another scan.
- Successful TAGGER tag mutations made after activation are intentional changes, not crosscheck discrepancies, and must not trigger a correction warning.
- If the crosscheck fails, retain the SQLite-derived view and report that verification failed without changing the files pane.

### Discovery progress indicator (low priority)

- Show a throttled running count of photos found while a folder or dropped-directory discovery is in progress.
- Keep the current initial background-discovery work's indeterminate loading presentation; do not make this follow-up a prerequisite.

### Evaluate the known-tags pane (low priority)

- Assess whether the persistent known-tags pane serves the keyboard-driven workflow or should be removed, replaced, or reduced in favor of autocomplete.
- Do not change its current behavior as part of background discovery and index I/O work.

### Error history command (low priority)

- Record tool errors with timestamps for the application session.
- Add an `:errors` command that shows all recorded errors, especially when multiple background operations have failed.
- Keep this separate from the initial background discovery and index I/O work, which reports errors only in the non-blocking footer.

### Review keyword length limits

- Determine the actual technical limits of the metadata formats and ExifTool.
- Decide whether TAGGER should validate or enforce a limit.

### AI-assisted tag suggestions

- Analyze a photo and propose tags for human approval.
- Define privacy, provider, cost, and review behavior before implementation.

### Improve multi-photo tagging workflow

- Basic multi-selection and tag mutation already exist.
- Evaluate whether selection, feedback, and partial-failure behavior are sufficient for practical batch tagging.

### Resumable background full-index refresh (low priority)

- Keep normal index updates incremental for changed photos.
- Run a full metadata refresh in small ExifTool batches and commit each batch with a durable SQLite checkpoint.
- Resume an interrupted refresh after application restart rather than beginning the full scan again.
- Show non-modal progress and resumed state while preserving usable searches against the last committed index snapshot.
- Keep confirmed tag mutations responsive; they must not wait behind the entire refresh.

## Removed from the active backlog

- A single source of truth for commands and shortcuts now exists in the action catalogue.
- Vim-style commands and key bindings are implemented.
- Edit-field `Ctrl+C` handling is implemented.
