# Backlog

## Product work

### IPTC-empty filter as a frozen snapshot

- Activating the filter captures the photos that are IPTC-empty at that moment.
- Tagging photos afterward must not remove them from the filtered list.
- Reapplying the filter is the only action that refreshes the snapshot.
- Implement after the behavior-preserving Photo Workspace refactor.

### Complete indexed reverse search

- The current SQLite/search implementation is only a partial prototype.
- Finish the intended search-result and restore behavior described in `INDEXING_PLAN.md`.
- Keep the normal folder-tagging workflow as the default.

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

## Personal tagging workflow (not product work)

- Finish tagging all bird photos.
- Decide useful categories and goals:
  - personal photos
  - aesthetically strong photos
  - record or evidence photos
  - educational details where a useful feature is visible despite poor image quality
  - quiz photos

## Removed from the active backlog

- A single source of truth for commands and shortcuts now exists in the action catalogue.
- Vim-style commands and key bindings are implemented.
- Edit-field `Ctrl+C` handling is implemented.
