# Exif UI (PyQt6)

Minimal GUI to view/add/remove photo keywords using `exiftool`.

Features (MVP)
- Drag and drop JPG/JPEG files (drop anywhere)
- Add folder button (includes subfolders)
- Image preview for selected file
- Capture date display (EXIF DateTimeOriginal)
- Shows canonical `IPTC:Keywords`; reads `XMP-dc:Subject` as a compatibility field
- Routine tag writes preserve an intentionally empty XMP field
- Offers a single-photo Resolve dialog for IPTC/XMP disagreements, with explicit copy and deletion choices for each field
- Tag autocomplete combines recent tags (last 100) with tags cached from the active index root
- Files-pane filters for indexed tags, capture date, filename (applied 700 ms after typing stops), exact ancestor-folder exclusions, and photos without IPTC keywords; after tagging, an IPTC-empty result remains available for one step back so its tags can be copied

Commands & shortcuts
- Command line: press `:` to open; `:ls`, `:list`, `:h`, `:help`, or `F1` list commands; `:q`/`:quit` quits; `Tab` completes
- `Esc` closes command line / exits text fields
- Focus: `Ctrl+W W` cycles the Files and current-tags panes; `Ctrl+W H/L` move focus between them
- Global focus (non-inputs): `i` add keyword, `f` files
- Tag input: `Tab` completes from the cached autocomplete vocabulary
- Files-pane filters: `Ctrl+T`, `Ctrl+D`, and `Ctrl+F` focus Tags, Date, and Filename; within the filter box, `Alt+T`, `Alt+D`, `Alt+F`, and `Alt+X` focus those controls and Exclude folder. `Alt+A` toggles filename case matching, `Alt+S` applies indexed search, and `Alt+C` clears every filter. `Ctrl+E` toggles Only without IPTC tags.
- Indexed search: pressing Enter in Tags or Date focuses the files pane on the first photo of an accepted non-empty result. `:search <query>` accepts bare tags, `tag:`, date queries (`date:YYYY`, `date:YYYY-MM`, `date:YYYY-MM-DD`, inclusive `date:YYYY-MM-DD..YYYY-MM-DD`, or `date:unknown`), and `tag:<tag> date:<date>` intersections. `:focusdatefilter`, `:focusfilenamefilter`, and `:focusexcludedir` focus their respective controls; `:filterfiles [--case] <query>` and `:clearfilenamefilter` control the workspace-local filename condition. `:excludedir <name>` adds an exact ancestor-folder exclusion and `:clearexcludedir <name>` removes one. `:clearfilters` clears every condition; `Ctrl+Shift+X`, `:clearsearch`/`:clear`, `:back`, or `Esc` in the file pane clear only indexed Tags/Date search and restore the preceding workspace view.
- Index: `:reindex` fully refreshes the active root in the background
- Lists: `j/k` move, `gg/G` top/bottom, `Home/End` also work
- Tags: `Shift+V` visual select, `Ctrl+C` yank selected tags, `Ctrl+V` paste (current file), `dd`/`Del`/`Backspace` delete selected tags
- File list: `Ctrl+C` or `Space y` yanks all tags from the current file; `Ctrl+V` or `Space p` pastes them onto the current file; `:open`/`Space O` opens selected photos (after an All/active Only/Cancel choice), `:opengimp`/`:gimp`/`Space G` opens them in GIMP, `:copypath`/`Space C` copies all selected Photo Workspace paths (one per line), and `:reveal`/`Space R` reveals the active path in the system file explorer
- Toggles: `Ctrl+Shift+B` keep *_original backups

Prerequisites
- Windows
- `exiftool` installed and available on PATH (running `exiftool -ver` must work)

Install
```bat
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Run
```bat
python tagger.py
```

Relocating the photo folder
---------------------------
TAGGER stores the SQLite index in `<photo-folder>\\.tagger\\index.sqlite`. When
photos are opened from a subfolder, TAGGER walks up to the highest ancestor that
already contains `.tagger` and reuses that index. If no such marker exists, it
uses the configured/default root when applicable, or the common photo-folder.
The actual tags remain in the photo metadata; the migration script only rewrites
the cached absolute paths. Close TAGGER first, make sure the photos are already
at the new location, then run a dry run followed by the migration:

```bat
python migrate_index.py "D:\\Fotos" "C:\\Users\\janwa\\Pictures\\Fotos" --database "C:\\Users\\janwa\\Pictures\\Fotos\\.tagger\\index.sqlite" --dry-run
python migrate_index.py "D:\\Fotos" "C:\\Users\\janwa\\Pictures\\Fotos" --database "C:\\Users\\janwa\\Pictures\\Fotos\\.tagger\\index.sqlite"
```

The second command creates a timestamped `index.sqlite.before-migration-*`
backup. Afterwards start TAGGER and run `:reindex` once to verify the index.

Notes
- TAGGER disables exiftool `*_original` backups by default. Enable the checkbox when a backup is wanted.
