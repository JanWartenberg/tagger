# Exif UI (PyQt6)

Minimal GUI to view/add/remove photo keywords using `exiftool`.

Features (MVP)
- Drag and drop JPG/JPEG files (drop anywhere)
- Add folder button (includes subfolders)
- Image preview for selected file
- Capture date display (EXIF DateTimeOriginal)
- Shows keywords (reads both `IPTC:Keywords` and `XMP-dc:Subject`)
- Writes keywords to both fields (keeps them in sync)
- Shows a mismatch warning if IPTC and XMP differ
- "Resolve" button to merge+sync both fields when they differ
- "Known tags": recent (last 100) + tags found in the same folder
- Recursive scan toggle for known tags (default OFF)
- Filter: show only files with empty IPTC keywords

Commands & shortcuts
- Command line: press `:` to open, `:ls` to list commands, `:q`/`:quit` to quit, `Tab` to complete
- `Esc` closes command line / exits text fields
- Focus: `Ctrl+W W` cycles panes, `Ctrl+W H/J/K/L` move focus
- Global focus (non-inputs): `i` add keyword, `t` known tags, `f` files
- Known tag filter: `/` or `Ctrl+F` focuses and selects text, `n/N` move in matches
- Lists: `j/k` move, `gg/G` top/bottom, `Home/End` also work
- Tags: `Shift+V` visual select, `Ctrl+C` yank, `Ctrl+V` paste (current file)
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

Legacy (optional):
```bat
python exif_ui.py
```

Notes
- By default exiftool creates `*_original` backup files. You can disable this via the checkbox.
