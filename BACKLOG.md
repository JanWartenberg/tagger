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
