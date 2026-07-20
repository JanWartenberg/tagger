import os
from pathlib import Path

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


def normalize_path(p: str) -> str:
    try:
        return str(Path(p).resolve())
    except Exception:
        return os.path.normpath(p)
