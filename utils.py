import os
from pathlib import Path

from PyQt6 import QtCore

SUPPORTED_EXTS = {".jpg", ".jpeg"}


def dedupe_casefold(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for s in items:
        s2 = s.strip()
        if not s2:
            continue
        key = s2.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(s2)
    return out


def extract_image_paths_from_urls(urls: list[QtCore.QUrl]) -> list[str]:
    paths: list[str] = []
    for u in urls:
        if not u.isLocalFile():
            continue
        p = Path(u.toLocalFile())
        if p.is_dir():
            for child in p.rglob("*"):
                if child.is_file() and child.suffix.lower() in SUPPORTED_EXTS:
                    paths.append(str(child))
        else:
            if p.suffix.lower() in SUPPORTED_EXTS:
                paths.append(str(p))
    return paths


def normalize_path(p: str) -> str:
    try:
        return str(Path(p).resolve())
    except Exception:
        return os.path.normpath(p)
