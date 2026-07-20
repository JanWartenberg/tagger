"""Qt-free coordination for background photo discovery.

The coordinator owns request identities and result eligibility.  Qt adapters submit
user intent and marshal the immutable events it emits back to the UI thread.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from threading import Lock
from typing import Protocol, TypeAlias


class DiscoveryAdapter(Protocol):
    """Traverses one folder and returns its discovered photo paths."""

    def discover(self, root: str) -> Iterable[str | Path]: ...


class IndexAdapter(Protocol):
    """Per-root index operations, implemented by the later index-I/O slices."""

    def is_initialized(self, root: str) -> bool: ...

    def sync(self, root: str, paths: Sequence[str]) -> object: ...

    def update_states(self, root: str, states: Mapping[str, object]) -> None: ...

    def search(self, root: str, query: str) -> Sequence[str]: ...

    def load_known_tags(self, root: str) -> set[str]: ...


class BackgroundRunner(Protocol):
    """Runs submitted work away from the caller's thread."""

    def submit(self, work: Callable[[], None]) -> None: ...


class DiscoveryKind(Enum):
    REPLACEMENT = "replacement"
    ADDITIVE = "additive"


@dataclass(frozen=True)
class DiscoveryRequest:
    """The identity assigned to one folder-discovery request."""

    kind: DiscoveryKind
    workspace_generation: int
    request_id: int
    root: str
    drop_sequence: int | None


@dataclass(frozen=True)
class DiscoveryCompleted:
    """An eligible discovery result; an empty ``paths`` tuple means no photos."""

    kind: DiscoveryKind
    workspace_generation: int
    request_id: int
    root: str
    paths: tuple[str, ...]
    drop_sequence: int | None


@dataclass(frozen=True)
class DiscoveryFailed:
    """An eligible discovery failure, without an exception object crossing threads."""

    kind: DiscoveryKind
    workspace_generation: int
    request_id: int
    root: str
    error: str
    drop_sequence: int | None


DiscoveryEvent: TypeAlias = DiscoveryCompleted | DiscoveryFailed


def _normalize_path(path: str | Path) -> str:
    try:
        return str(Path(path).resolve())
    except OSError:
        return str(Path(path))


class BackgroundCoordinator:
    """Schedules folder discovery and publishes only current, ordered results.

    Replacement discovery starts a new workspace generation immediately. Additive
    discoveries belong to the current generation and are released in the order
    their drops began, independent of completion order.
    """

    def __init__(
        self,
        *,
        discovery: DiscoveryAdapter,
        index: IndexAdapter,
        runner: BackgroundRunner,
        event_sink: Callable[[DiscoveryEvent], None],
    ) -> None:
        self._discovery = discovery
        self._index = index
        self._runner = runner
        self._event_sink = event_sink
        self._lock = Lock()
        self._workspace_generation = 0
        self._next_request_id = 0
        self._current_replacement_request_id: int | None = None
        self._next_drop_sequence = 0
        self._next_released_drop_sequence = 0
        self._completed_drops: dict[int, DiscoveryEvent] = {}

    def replace_workspace_from_folder(self, root: str | Path) -> DiscoveryRequest:
        """Start a replacement discovery, invalidating all older workspace work."""
        with self._lock:
            self._workspace_generation += 1
            self._current_replacement_request_id = self._new_request_id()
            self._next_drop_sequence = 0
            self._next_released_drop_sequence = 0
            self._completed_drops.clear()
            request = DiscoveryRequest(
                kind=DiscoveryKind.REPLACEMENT,
                workspace_generation=self._workspace_generation,
                request_id=self._current_replacement_request_id,
                root=_normalize_path(root),
                drop_sequence=None,
            )
        self._schedule(request)
        return request

    def add_dropped_directory(self, root: str | Path) -> DiscoveryRequest:
        """Start discovery to append to the current workspace when it completes."""
        with self._lock:
            request = DiscoveryRequest(
                kind=DiscoveryKind.ADDITIVE,
                workspace_generation=self._workspace_generation,
                request_id=self._new_request_id(),
                root=_normalize_path(root),
                drop_sequence=self._next_drop_sequence,
            )
            self._next_drop_sequence += 1
        self._schedule(request)
        return request

    def _new_request_id(self) -> int:
        request_id = self._next_request_id
        self._next_request_id += 1
        return request_id

    def _schedule(self, request: DiscoveryRequest) -> None:
        def work() -> None:
            try:
                paths = tuple(
                    _normalize_path(path)
                    for path in self._discovery.discover(request.root)
                )
            except Exception as error:
                event: DiscoveryEvent = DiscoveryFailed(
                    kind=request.kind,
                    workspace_generation=request.workspace_generation,
                    request_id=request.request_id,
                    root=request.root,
                    error=str(error),
                    drop_sequence=request.drop_sequence,
                )
            else:
                event = DiscoveryCompleted(
                    kind=request.kind,
                    workspace_generation=request.workspace_generation,
                    request_id=request.request_id,
                    root=request.root,
                    paths=paths,
                    drop_sequence=request.drop_sequence,
                )
            self._accept(event)

        self._runner.submit(work)

    def _accept(self, event: DiscoveryEvent) -> None:
        with self._lock:
            if event.workspace_generation != self._workspace_generation:
                return
            if event.kind is DiscoveryKind.REPLACEMENT:
                if event.request_id != self._current_replacement_request_id:
                    return
                events = [event]
            else:
                if event.drop_sequence is None:
                    return
                self._completed_drops[event.drop_sequence] = event
                events = []
                while self._next_released_drop_sequence in self._completed_drops:
                    events.append(
                        self._completed_drops.pop(self._next_released_drop_sequence)
                    )
                    self._next_released_drop_sequence += 1

        for accepted in events:
            self._event_sink(accepted)
