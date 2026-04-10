# Indexing Plan (D:\Fotos)

Goal: fast tag/date search for 1–3k photos without UI blocking.

## Scope
- One DB per root folder (e.g., `D:\Fotos`).
- Store: tags + capture date (what the UI uses).

## Storage choice
- **SQLite** (recommended): robust, fast queries, incremental updates.
- Location: `D:\Fotos\.exif_ui\index.sqlite`.

## Schema (minimal)
```
photos(
  path TEXT PRIMARY KEY,
  mtime INTEGER,
  size INTEGER,
  tags_json TEXT,
  date_taken TEXT
)

tags(
  tag TEXT,
  path TEXT
)
```
- Optional indices: `tags(tag)`, `photos(date_taken)`.

## Indexer flow
- On tool start: check last index time. If >24h, start background scan.
- Incremental scan: only files with changed `mtime/size` are re-read.
- UI stays responsive; status bar shows progress.
- Manual `:reindex` to force full scan.

## Update hooks
- When tags are written in the UI, update DB immediately.
- Avoid waiting for the next scan.

## Query
- UI search queries **only** the DB (no live exiftool scan).

## Scheduling options
- In-app background worker is enough (no Windows cron needed).
- Optional external script + Task Scheduler if indexing must happen without UI.
