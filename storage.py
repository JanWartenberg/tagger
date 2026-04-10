import json
import os
from pathlib import Path

APP_DIR_NAME = "exif_ui"
LEGACY_APP_DIR_NAME = "exif_keywords_mvp"


def _app_data_dir() -> Path:
    base = os.getenv("APPDATA") or str(Path.home())
    d = Path(base) / APP_DIR_NAME
    d.mkdir(parents=True, exist_ok=True)
    return d


def _recent_tags_path() -> Path:
    return _app_data_dir() / "recent_tags.json"


def _legacy_recent_tags_path() -> Path:
    base = os.getenv("APPDATA") or str(Path.home())
    return Path(base) / LEGACY_APP_DIR_NAME / "recent_tags.json"


def load_recent_tags() -> list[str]:
    p = _recent_tags_path()
    if not p.exists():
        legacy = _legacy_recent_tags_path()
        if legacy.exists():
            try:
                data = json.loads(legacy.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    tags: list[str] = []
                    for x in data:
                        if isinstance(x, str) and x.strip():
                            tags.append(x.strip())
                    save_recent_tags(tags)
                    return tags[:100]
            except Exception:
                pass
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return []
    if not isinstance(data, list):
        return []
    out: list[str] = []
    for x in data:
        if isinstance(x, str) and x.strip():
            out.append(x.strip())
    return out[:100]


def save_recent_tags(tags: list[str]) -> None:
    p = _recent_tags_path()
    p.write_text(json.dumps(tags[:100], ensure_ascii=True, indent=2), encoding="utf-8")


def add_recent_tag(tag: str) -> None:
    tag = tag.strip()
    if not tag:
        return
    tags = load_recent_tags()
    tags = [t for t in tags if t.lower() != tag.lower()]
    tags.insert(0, tag)
    save_recent_tags(tags)


def _config_path() -> Path:
    return _app_data_dir() / "config.json"


def load_config() -> dict:
    p = _config_path()
    if not p.exists():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def save_config(cfg: dict) -> None:
    p = _config_path()
    p.write_text(json.dumps(cfg, ensure_ascii=True, indent=2), encoding="utf-8")
