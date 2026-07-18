"""Qt-free state model for the Photo Workspace."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable


class PhotoWorkspaceViewMode(str, Enum):
    """The logical view currently shown by the Photo Workspace."""

    NORMAL = "normal"
    IPTC_EMPTY = "iptc_empty"
    DATABASE_SEARCH = "database_search"


@dataclass(frozen=True)
class PhotoWorkspaceSnapshot:
    """Immutable state needed to render the Photo Workspace."""

    paths: tuple[str, ...]
    visible_paths: tuple[str, ...]
    selected_paths: tuple[str, ...]
    active_path: str | None
    view_mode: PhotoWorkspaceViewMode = PhotoWorkspaceViewMode.NORMAL
    filter_operation_id: int | None = None
    filter_processed: int = 0
    filter_total: int = 0
    iptc_empty_filter_active: bool = False
    filter_view_switched: bool = False
    database_search_active: bool = False


@dataclass(frozen=True)
class IptcEmptyFilterBatch:
    """Metadata work requested by an IPTC-empty filter operation."""

    operation_id: int
    paths: tuple[str, ...]


class PhotoWorkspace:
    """Owns Photo Workspace membership, selection, and filter state."""

    def __init__(self) -> None:
        self._paths: list[str] = []
        self._visible: set[str] = set()
        self._selected: set[str] = set()
        self._view_mode = PhotoWorkspaceViewMode.NORMAL

        self._operation = 0
        self._filter_running = False
        self._batches: list[tuple[str, ...]] = []
        self._inflight: IptcEmptyFilterBatch | None = None
        self._processed = 0
        self._matches: set[str] = set()
        self._switched = False
        self._baseline_visible: set[str] = set()
        self._baseline_selected: set[str] = set()

    def snapshot(self) -> PhotoWorkspaceSnapshot:
        """Return the immutable state used to render the workspace."""
        visible = tuple(path for path in self._paths if path in self._visible)
        selected = tuple(path for path in visible if path in self._selected)
        return PhotoWorkspaceSnapshot(
            paths=tuple(self._paths),
            visible_paths=visible,
            selected_paths=selected,
            active_path=selected[0] if selected else None,
            view_mode=self._view_mode,
            filter_operation_id=self._operation if self._filter_running else None,
            filter_processed=self._processed,
            filter_total=len(self._paths),
            iptc_empty_filter_active=(
                self._view_mode is PhotoWorkspaceViewMode.IPTC_EMPTY
            ),
            filter_view_switched=self._switched,
            database_search_active=(
                self._view_mode is PhotoWorkspaceViewMode.DATABASE_SEARCH
            ),
        )

    def add_paths(self, paths: Iterable[str]) -> PhotoWorkspaceSnapshot:
        """Add normalized paths while preserving insertion order."""
        known = set(self._paths)
        for path in paths:
            if path not in known:
                known.add(path)
                self._paths.append(path)
                self._visible.add(path)
        self._repair_selection()
        return self.snapshot()

    def reload_paths(self, paths: Iterable[str]) -> PhotoWorkspaceSnapshot:
        """Replace all workspace state and invalidate outstanding filter work."""
        self._operation += 1
        self._paths = []
        self._visible = set()
        self._selected = set()
        self._view_mode = PhotoWorkspaceViewMode.NORMAL
        self._filter_running = False
        self._batches = []
        self._inflight = None
        self._processed = 0
        self._matches = set()
        self._switched = False
        self._baseline_visible = set()
        self._baseline_selected = set()
        return self.add_paths(paths)

    def select_paths(self, paths: Iterable[str]) -> PhotoWorkspaceSnapshot:
        """Apply a user selection and repair it against the visible paths."""
        self._selected = set(paths) & self._visible
        if self._filter_running:
            self._baseline_visible = set(self._visible)
            self._baseline_selected = set(self._selected)
        return self.snapshot()

    def set_visible_paths(self, paths: Iterable[str]) -> PhotoWorkspaceSnapshot:
        """Set the visible paths for an externally supplied logical view."""
        self._view_mode = PhotoWorkspaceViewMode.NORMAL
        self._visible = set(paths) & set(self._paths)
        self._repair_selection()
        return self.snapshot()

    def apply_database_search_matches(
        self, matching_paths: Iterable[str]
    ) -> PhotoWorkspaceSnapshot:
        """Show loaded database-search matches and invalidate IPTC filter work."""
        self.clear_iptc_empty_filter()
        self._view_mode = PhotoWorkspaceViewMode.DATABASE_SEARCH
        self._visible = set(matching_paths) & set(self._paths)
        self._repair_selection()
        return self.snapshot()

    def clear_database_search(self) -> PhotoWorkspaceSnapshot:
        """Clear the database-search view and restore all loaded paths."""
        self._view_mode = PhotoWorkspaceViewMode.NORMAL
        self._visible = set(self._paths)
        self._repair_selection()
        return self.snapshot()

    def start_iptc_empty_filter(
        self, first_size: int, batch_size: int
    ) -> PhotoWorkspaceSnapshot:
        """Start an IPTC-empty operation and prepare its metadata batches."""
        self._operation += 1
        self._view_mode = PhotoWorkspaceViewMode.IPTC_EMPTY
        self._filter_running = True
        self._inflight = None
        self._processed = 0
        self._matches = set()
        self._switched = False
        self._baseline_visible = set(self._visible)
        self._baseline_selected = set(self._selected)
        self._visible = set(self._paths)

        first_size = max(1, first_size)
        batch_size = max(1, batch_size)
        first = self._paths[:first_size]
        rest = self._paths[first_size:]
        self._batches = [tuple(first)] if first else []
        self._batches.extend(
            tuple(rest[index : index + batch_size])
            for index in range(0, len(rest), batch_size)
        )
        if not self._batches:
            self._filter_running = False
        return self.snapshot()

    def clear_iptc_empty_filter(self) -> PhotoWorkspaceSnapshot:
        """Disable the filter and invalidate every outstanding batch result."""
        self._operation += 1
        self._view_mode = PhotoWorkspaceViewMode.NORMAL
        self._filter_running = False
        self._batches = []
        self._inflight = None
        self._processed = 0
        self._matches = set()
        self._switched = False
        self._visible = set(self._paths)
        self._repair_selection()
        return self.snapshot()

    def next_iptc_empty_filter_batch(self) -> IptcEmptyFilterBatch | None:
        """Return the next requested metadata batch, if one is available."""
        if not self._filter_running or self._inflight is not None or not self._batches:
            return None
        self._inflight = IptcEmptyFilterBatch(self._operation, self._batches.pop(0))
        return self._inflight

    def accepts_iptc_empty_filter_result(self, operation_id: int) -> bool:
        """Return whether a result belongs to the active metadata batch."""
        batch = self._inflight
        return (
            self._filter_running
            and batch is not None
            and operation_id == self._operation == batch.operation_id
        )

    def accept_iptc_empty_filter_batch(
        self, operation_id: int, empty_paths: Iterable[str]
    ) -> PhotoWorkspaceSnapshot:
        """Apply a metadata result only when it belongs to the active batch."""
        batch = self._inflight
        if not self.accepts_iptc_empty_filter_result(operation_id):
            return self.snapshot()

        self._inflight = None
        self._processed += len(batch.paths)
        self._matches.update(set(empty_paths) & set(batch.paths))
        if self._matches:
            self._switched = True
            self._visible = set(self._matches)
            self._repair_selection()
        elif not self._batches:
            self._visible = set()
            self._repair_selection()

        self._baseline_visible = set(self._visible)
        self._baseline_selected = set(self._selected)
        if not self._batches:
            self._filter_running = False
        return self.snapshot()

    def fail_iptc_empty_filter_batch(self, operation_id: int) -> PhotoWorkspaceSnapshot:
        """Stop a failed operation and restore its last successful view."""
        batch = self._inflight
        if (
            self._filter_running
            and batch is not None
            and operation_id == self._operation == batch.operation_id
        ):
            self._visible = set(self._baseline_visible)
            self._selected = set(self._baseline_selected)
            self._filter_running = False
            self._batches = []
            self._inflight = None
            self._repair_selection()
        return self.snapshot()

    def apply_iptc_emptiness(
        self, emptiness_by_path: dict[str, bool]
    ) -> PhotoWorkspaceSnapshot:
        """Keep the current IPTC-empty view stable after metadata mutations."""
        del emptiness_by_path
        return self.snapshot()

    def _repair_selection(self) -> None:
        self._selected &= self._visible
        if not self._selected and self._visible:
            self._selected.add(
                next(path for path in self._paths if path in self._visible)
            )
