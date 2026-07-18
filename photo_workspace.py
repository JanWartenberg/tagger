"""Qt-free state model for the Photo Workspace."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class PhotoWorkspaceSnapshot:
    """Immutable state needed to render the Photo Workspace."""

    paths: tuple[str, ...]
    visible_paths: tuple[str, ...]
    selected_paths: tuple[str, ...]
    active_path: str | None


class PhotoWorkspace:
    """Owns Photo Workspace membership, visibility, and ordered selection."""

    def __init__(self) -> None:
        self._paths: list[str] = []
        self._visible_paths: set[str] = set()
        self._selected_paths: set[str] = set()

    def snapshot(self) -> PhotoWorkspaceSnapshot:
        visible_paths = tuple(path for path in self._paths if path in self._visible_paths)
        selected_paths = tuple(path for path in visible_paths if path in self._selected_paths)
        active_path = selected_paths[0] if selected_paths else None
        return PhotoWorkspaceSnapshot(
            paths=tuple(self._paths),
            visible_paths=visible_paths,
            selected_paths=selected_paths,
            active_path=active_path,
        )

    def add_paths(self, paths: Iterable[str]) -> PhotoWorkspaceSnapshot:
        known_paths = set(self._paths)
        for path in paths:
            if path in known_paths:
                continue
            known_paths.add(path)
            self._paths.append(path)
            self._visible_paths.add(path)
        if not self._selected_paths and self._visible_paths:
            self._selected_paths.add(next(path for path in self._paths if path in self._visible_paths))
        return self.snapshot()

    def reload_paths(self, paths: Iterable[str]) -> PhotoWorkspaceSnapshot:
        self._paths = []
        self._visible_paths = set()
        self._selected_paths = set()
        self.add_paths(paths)
        return self.snapshot()

    def select_paths(self, paths: Iterable[str]) -> PhotoWorkspaceSnapshot:
        selected = set(paths)
        self._selected_paths = selected & self._visible_paths
        return self.snapshot()

    def set_visible_paths(self, paths: Iterable[str]) -> PhotoWorkspaceSnapshot:
        self._visible_paths = set(paths) & set(self._paths)
        self._selected_paths &= self._visible_paths
        if not self._selected_paths and self._visible_paths:
            self._selected_paths.add(next(path for path in self._paths if path in self._visible_paths))
        return self.snapshot()
