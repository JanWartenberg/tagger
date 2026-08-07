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
- "Known tags": recent (last 100) + tags found in the same folder
- Recursive scan toggle for known tags (default OFF)
- Filter: show only files with empty IPTC keywords; after tagging, the image remains available for one step back so its tags can be copied

Commands & shortcuts
- Command line: press `:` to open; `:ls`, `:list`, `:h`, `:help`, or `F1` list commands; `:q`/`:quit` quits; `Tab` completes
- `Esc` closes command line / exits text fields
- Focus: `Ctrl+W W` cycles panes, `Ctrl+W H/J/K/L` move focus
- Global focus (non-inputs): `i` add keyword, `t` known tags, `f` files
- Known tag filter: `/` or `Ctrl+F` focuses and selects text, `n/N` move in matches
- Photo-tag search: `Ctrl+Shift+F` focuses and selects the DB tag/date search text; pressing Enter focuses the files pane on the first photo of an accepted non-empty result; `:search <query>` runs an indexed `tag:`, bare-tag, or date search (`date:YYYY`, `date:YYYY-MM`, `date:YYYY-MM-DD`, inclusive `date:YYYY-MM-DD..YYYY-MM-DD`, or `date:unknown`); `Ctrl+Shift+X`, `:clearsearch`/`:clear`, `:back`, or `Esc` in the file pane restores the folder view
- Index: `:reindex` fully refreshes the active root in the background
- Lists: `j/k` move, `gg/G` top/bottom, `Home/End` also work
- Tags: `Shift+V` visual select, `Ctrl+C` yank selected tags, `Ctrl+V` paste (current file), `dd`/`Del`/`Backspace` delete selected tags
- File list: `Ctrl+C` or `Space y` yanks all tags from the current file; `Ctrl+V` or `Space p` pastes them onto the current file; `:open`/`Space O` opens selected photos (after an All/active Only/Cancel choice), `:opengimp`/`:gimp`/`Space G` opens them in GIMP, `:copypath`/`Space C` copies all selected Photo Workspace paths (one per line), and `:reveal`/`Space R` reveals the active path in the system file explorer
- Toggles: `Ctrl+Shift+B` keep *_original backups, `Ctrl+Shift+E` only IPTC-empty

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

Notes
- TAGGER disables exiftool `*_original` backups by default. Enable the checkbox when a backup is wanted.
