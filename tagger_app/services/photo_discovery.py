"""Filesystem adapter for discovering supported photo files."""

from __future__ import annotations

import os
from pathlib import Path

from tagger_app.utils import SUPPORTED_EXTS

SUPPORTED_PHOTO_EXTENSIONS = SUPPORTED_EXTS


class FileSystemPhotoDiscovery:
    """Discover supported photo paths below one selected directory."""

    def discover(self, root: str) -> list[str]:
        return self._discover(root, include_file_links=True)

    def discover_refresh(self, root: str) -> list[str]:
        """Enumerate a physical subtree without following file links."""
        return self._discover(root, include_file_links=False)

    def _discover(self, root: str, *, include_file_links: bool) -> list[str]:
        # Partial enumeration must not become evidence for deleting index rows.
        pending = [Path(root)]
        physical_root = Path(root).resolve(strict=True)
        visited: set[Path] = set()
        paths = []
        while pending:
            directory = pending.pop()
            physical = directory.resolve(strict=True)
            if physical in visited or (
                not include_file_links and not physical.is_relative_to(physical_root)
            ):
                continue
            visited.add(physical)
            with os.scandir(directory) as entries:
                for entry in entries:
                    if entry.is_symlink() and not include_file_links:
                        continue
                    if entry.is_dir(follow_symlinks=False):
                        pending.append(Path(entry.path))
                    elif Path(
                        entry.name
                    ).suffix.lower() in SUPPORTED_PHOTO_EXTENSIONS and entry.is_file(
                        follow_symlinks=include_file_links
                    ):
                        photo = Path(entry.path).resolve(strict=True)
                        if include_file_links or photo.is_relative_to(physical_root):
                            paths.append(str(photo))
        return paths
