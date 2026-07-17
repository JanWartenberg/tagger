# Indexing Plan (D:\Fotos)

> **Status:** This is a future-state plan and has not been fully implemented. During behavior-preserving refactors, the current executable behavior is authoritative; do not treat this document as the existing behavior specification.

Goal: fast tag/date search for 1–3k photos without UI blocking.

## Scope
- One DB per root folder (e.g., `D:\Fotos`).
- Store: tags + capture date (what the UI uses).

## Storage choice
- **SQLite** (recommended): robust, fast queries, incremental updates.
- Location: `D:\Fotos\.tagger\index.sqlite`.

## Schema (minimal)
```
photos(
  path TEXT PRIMARY KEY,
  mtime INTEGER,
  size INTEGER,
  date_taken TEXT
)

tags(
  id INTEGER PRIMARY KEY,
  tag TEXT UNIQUE
)

photo_tags(
  photo_path TEXT,
  tag_id INTEGER,
  PRIMARY KEY(photo_path, tag_id)
)
```
- Optional indices: `tags(tag)`, `photos(date_taken)`, `photo_tags(tag_id)`, `photo_tags(photo_path)`.

## Indexer flow
- On tool start: check last index time. If >24h, start background scan.
- Incremental scan: only files with changed `mtime/size` are re-read.
- UI stays responsive; status bar shows progress.
- Manual `:reindex` to force full scan.
- Deletions: after scan, remove DB rows for files that no longer exist on disk.
- Renames: treated as delete + new file unless a future move-detection is added.

## Update hooks
- When tags are written in the UI, update DB immediately.
- Avoid waiting for the next scan.
- Keep `photos`, `tags`, and `photo_tags` in one transaction.

## Query
- UI search queries **only** the DB (no live exiftool scan).
- "Tags for photo X" -> `photo_tags` joined with `tags`.
- "Photos with tag foo" -> `tags` joined with `photo_tags`.

### Reverse search mini-spec (UI)
Goal: keep the existing tagger workflow as default; reverse search is a temporary results mode.

#### Modes
- **Folder mode**: current behavior. A folder is opened, optional IPTC-empty filter is applied, and the user steps through files one by one to tag them.
- **Search-result mode**: the left file pane is replaced with DB matches for a query (e.g. tag search).
- **Restore mode**: `Esc` / `:back` / `Clear` returns to the previous folder list.

#### Commands / input
- `:search <query>`: run a DB search and show matching photos in the file pane.
- `:back`: restore the previous folder view.
- `:clearsearch`: clear search and restore the folder view.
- Search syntax (initial):
  - `tag:foo` -> photos with tag containing `foo`
  - `date:2024` -> photos whose stored capture date contains `2024`
  - bare `foo` -> treated like a tag search

#### Behavior
- Search results are shown in the **existing file list pane**; no separate results widget is required.
- Keyboard navigation stays unchanged: `j/k`, `gg/G`, `Home/End`, `Ctrl+V`, `Ctrl+C`, etc.
- Tagging actions continue to work on the selected photo(s) from the result list.
- Search mode must not remove the current folder from the app; it is only a view/state switch.
- `Clear` should mean “remove DB filter / show the active folder list again”, not “show all indexed photos globally”.

#### State requirements
- Preserve the previous folder list, current selection, and scroll position while a search is active.
- A search must not destroy the normal folder workflow.
- Search results should be selectable and usable like normal file-list entries.

### SQL examples
```sql
-- Tags for one photo
SELECT t.tag
FROM tags t
JOIN photo_tags pt ON pt.tag_id = t.id
WHERE pt.photo_path = ?
ORDER BY t.tag;

-- Photos that have one tag
SELECT p.path
FROM photos p
JOIN photo_tags pt ON pt.photo_path = p.path
JOIN tags t ON t.id = pt.tag_id
WHERE t.tag = ?
ORDER BY p.path;
```

## Scheduling options
- In-app background worker is enough (no Windows cron needed).
- Optional external script + Task Scheduler if indexing must happen without UI.
