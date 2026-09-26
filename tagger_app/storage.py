import json
import os
from pathlib import Path

# --- Storage constants (no magic strings in code) ---
ENV_APPDATA = "APPDATA"
APP_DIR_NAME = "tagger"

CONFIG_FILENAME = "config.json"
RECENT_TAGS_FILENAME = "recent_tags.json"
MAX_RECENT_TAGS = 100
TEXT_ENCODING = "utf-8"


def _base_storage_dir() -> Path:
    base = os.getenv(ENV_APPDATA)
    return Path(base) if base else Path.home()


def _storage_dir(app_dir_name: str, ensure_exists: bool) -> Path:
    d = _base_storage_dir() / app_dir_name
    if ensure_exists:
        d.mkdir(parents=True, exist_ok=True)
    return d


def _path_in_storage(app_dir_name: str, filename: str, ensure_dir: bool) -> Path:
    return _storage_dir(app_dir_name, ensure_exists=ensure_dir) / filename


def _recent_tags_path() -> Path:
    return _path_in_storage(APP_DIR_NAME, RECENT_TAGS_FILENAME, ensure_dir=True)


def _config_path() -> Path:
    return _path_in_storage(APP_DIR_NAME, CONFIG_FILENAME, ensure_dir=True)


def describe_storage_paths() -> dict[str, str]:
    """Useful for debugging: where does the app read/write things?"""
    return {
        "base_storage_dir": str(_base_storage_dir()),
        "app_dir": str(_storage_dir(APP_DIR_NAME, ensure_exists=False)),
        "config_path": str(_config_path()),
        "recent_tags_path": str(_recent_tags_path()),
    }


def load_recent_tags() -> list[str]:
    def _clean_list(data: object) -> list[str]:
        if not isinstance(data, list):
            return []
        out: list[str] = []
        for x in data:
            if isinstance(x, str) and x.strip():
                out.append(x.strip())
        return out[:MAX_RECENT_TAGS]

    def _read_list(path: Path) -> list[str]:
        try:
            data = json.loads(path.read_text(encoding=TEXT_ENCODING))
        except (OSError, UnicodeError, json.JSONDecodeError):
            return []
        return _clean_list(data)

    current = _recent_tags_path()
    return _read_list(current) if current.exists() else []


def save_recent_tags(tags: list[str]) -> None:
    p = _recent_tags_path()
    p.write_text(
        json.dumps(tags[:MAX_RECENT_TAGS], ensure_ascii=True, indent=2),
        encoding=TEXT_ENCODING,
    )


def add_recent_tag(tag: str) -> None:
    tag = tag.strip()
    if not tag:
        return
    tags = load_recent_tags()
    tags = [t for t in tags if t.lower() != tag.lower()]
    tags.insert(0, tag)
    save_recent_tags(tags)


def load_config() -> dict:
    p = _config_path()
    if not p.exists():
        return {}
    try:
        data = json.loads(p.read_text(encoding=TEXT_ENCODING))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def save_config(cfg: dict) -> None:
    p = _config_path()
    p.write_text(json.dumps(cfg, ensure_ascii=True, indent=2), encoding=TEXT_ENCODING)
