"""Filesystem adapter for discovering supported photo files."""

from __future__ import annotations

from pathlib import Path

SUPPORTED_PHOTO_EXTENSIONS = {".jpg", ".jpeg"}


class FileSystemPhotoDiscovery:
    """Discover supported photo paths below one selected directory."""

    def discover(self, root: str) -> list[str]:
        return [
            str(path)
            for path in Path(root).rglob("*")
            if path.is_file() and path.suffix.lower() in SUPPORTED_PHOTO_EXTENSIONS
        ]
