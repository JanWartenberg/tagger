# Exif UI (PyQt6)

Minimal GUI to view/add/remove photo keywords using `exiftool`.

Features (MVP)
- Drag and drop JPG/JPEG files (drop anywhere)
- Image preview for selected file
- Shows keywords (reads both `IPTC:Keywords` and `XMP-dc:Subject`)
- Writes keywords to both fields (keeps them in sync)
- Shows a mismatch warning if IPTC and XMP differ
- "Resolve" button to merge+sync both fields when they differ
- "Known tags": recent (last 100) + tags found in the same folder

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
python exif_ui.py
```

Notes
- By default exiftool creates `*_original` backup files. You can disable this via the checkbox.
