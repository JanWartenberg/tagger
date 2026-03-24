"""Backward-compatible entrypoint.

Use `python exif_ui.py` instead.
"""

from exif_ui import main


if __name__ == "__main__":
    raise SystemExit(main())
