"""Qt-free state model for the Photo Workspace."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable

@dataclass(frozen=True)
class PhotoWorkspaceSnapshot:
    paths: tuple[str, ...]
    visible_paths: tuple[str, ...]
    selected_paths: tuple[str, ...]
    active_path: str | None
    filter_operation_id: int | None = None
    filter_processed: int = 0

@dataclass(frozen=True)
class IptcEmptyFilterBatch:
    operation_id: int
    paths: tuple[str, ...]

class PhotoWorkspace:
    def __init__(self) -> None:
        self._paths: list[str] = []
        self._visible: set[str] = set()
        self._selected: set[str] = set()
        self._operation = 0
        self._filtering = False
        self._batches: list[tuple[str, ...]] = []
        self._inflight: IptcEmptyFilterBatch | None = None
        self._processed = 0
        self._matches: set[str] = set()
        self._switched = False
        self._baseline_visible: set[str] = set()
        self._baseline_selected: set[str] = set()
        self._preserved: set[str] = set()
        self._previous_selection: set[str] = set()

    def snapshot(self) -> PhotoWorkspaceSnapshot:
        visible = tuple(path for path in self._paths if path in self._visible)
        selected = tuple(path for path in visible if path in self._selected)
        return PhotoWorkspaceSnapshot(tuple(self._paths), visible, selected, selected[0] if selected else None, self._operation if self._filtering else None, self._processed)

    def add_paths(self, paths: Iterable[str]) -> PhotoWorkspaceSnapshot:
        known = set(self._paths)
        for path in paths:
            if path not in known:
                known.add(path); self._paths.append(path); self._visible.add(path)
        self._repair_selection()
        return self.snapshot()

    def reload_paths(self, paths: Iterable[str]) -> PhotoWorkspaceSnapshot:
        self.__init__()
        return self.add_paths(paths)

    def select_paths(self, paths: Iterable[str]) -> PhotoWorkspaceSnapshot:
        self._selected = set(paths) & self._visible
        if self._filtering:
            allowed = self._selected | self._previous_selection
            released = self._preserved - allowed
            self._preserved &= allowed; self._matches -= released
            if self._switched: self._visible -= released
            self._previous_selection = set(self._selected)
            self._repair_selection()
        return self.snapshot()

    def set_visible_paths(self, paths: Iterable[str]) -> PhotoWorkspaceSnapshot:
        self._visible = set(paths) & set(self._paths); self._repair_selection(); return self.snapshot()

    def start_iptc_empty_filter(self, first_size: int, batch_size: int) -> PhotoWorkspaceSnapshot:
        self._operation += 1; self._filtering = True; self._inflight = None; self._processed = 0; self._matches = set(); self._switched = False
        self._baseline_visible = set(self._visible); self._baseline_selected = set(self._selected); self._preserved = set(); self._previous_selection = set(self._selected); self._visible = set(self._paths)
        first_size, batch_size = max(1, first_size), max(1, batch_size)
        first, rest = self._paths[:first_size], self._paths[first_size:]
        self._batches = [tuple(first)] if first else []
        self._batches += [tuple(rest[i:i + batch_size]) for i in range(0, len(rest), batch_size)]
        return self.snapshot()

    def next_iptc_empty_filter_batch(self) -> IptcEmptyFilterBatch | None:
        if not self._filtering or self._inflight or not self._batches: return None
        self._inflight = IptcEmptyFilterBatch(self._operation, self._batches.pop(0)); return self._inflight

    def accept_iptc_empty_filter_batch(self, operation_id: int, empty_paths: Iterable[str]) -> PhotoWorkspaceSnapshot:
        batch = self._inflight
        if not self._filtering or batch is None or operation_id != self._operation: return self.snapshot()
        self._inflight = None; self._processed += len(batch.paths); self._matches |= (set(empty_paths) & set(batch.paths)) | self._preserved
        if self._matches: self._switched = True; self._visible = set(self._matches); self._repair_selection()
        elif not self._batches: self._visible = set(); self._repair_selection()
        return self.snapshot()

    def fail_iptc_empty_filter_batch(self, operation_id: int) -> PhotoWorkspaceSnapshot:
        if self._filtering and operation_id == self._operation:
            self._visible = self._baseline_visible; self._selected = self._baseline_selected; self._filtering = False; self._batches = []; self._inflight = None
        return self.snapshot()

    def preserve_selected_paths_after_tagging(self, paths: Iterable[str]) -> PhotoWorkspaceSnapshot:
        if self._filtering:
            self._preserved |= set(paths) & set(self._paths); self._matches |= self._preserved
            if self._switched: self._visible |= self._preserved
        return self.snapshot()

    def _repair_selection(self) -> None:
        self._selected &= self._visible
        if not self._selected and self._visible: self._selected.add(next(path for path in self._paths if path in self._visible))
