"""Qt-free coordination for background discovery and index I/O."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from threading import Lock
from typing import Protocol, TypeAlias


class DiscoveryAdapter(Protocol):
    """Traverses one folder and returns its discovered photo paths."""

    def discover(self, root: str) -> Iterable[str | Path]: ...


class IndexAdapter(Protocol):
    """Per-root index operations performed only by the Coordinator's workers."""

    def is_initialized(self, root: str) -> bool: ...

    def needs_keyword_index_rebuild(self, root: str) -> bool: ...

    def is_refresh_stale(self, root: str) -> bool: ...

    def sync(self, root: str, paths: Sequence[str]) -> object: ...

    def refresh(self, root: str) -> object: ...

    def restart_refresh(self, root: str) -> object: ...

    def cancel_refresh(self, root: str) -> bool: ...

    def remove_photo(self, root: str, path: str) -> object: ...

    def reconcile_directory(self, root: str, directory: str) -> object: ...

    def index_missing(self, root: str, paths: Sequence[str]) -> int: ...

    def update_states(self, root: str, states: Mapping[str, object]) -> None: ...

    def search(self, root: str, query: str) -> Sequence[str]: ...

    def load_iptc_empty(self, root: str, candidate_paths: Sequence[str]) -> object: ...

    def load_known_tags(self, root: str) -> set[str]: ...


class BackgroundRunner(Protocol):
    """Runs submitted work away from the caller's thread."""

    def submit(self, work: Callable[[], None]) -> None: ...


class DiscoveryKind(Enum):
    REPLACEMENT = "replacement"
    ADDITIVE = "additive"


class IndexOperationKind(Enum):
    ENSURE = "ensure"
    REFRESH_IF_STALE = "refresh_if_stale"
    FULL_REINDEX = "full_reindex"
    INDEX_MISSING = "index_missing"
    UPDATE_STATES = "update_states"
    CANCEL_REFRESH = "cancel_refresh"


class IndexRefreshKind(Enum):
    AUTOMATIC = "automatic"
    MANUAL = "manual"
    STALE_RESULT_REPAIR = "stale_result_repair"


class IndexReadKind(Enum):
    SEARCH = "search"
    IPTC_EMPTY = "iptc_empty"
    KNOWN_TAGS = "known_tags"


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


@dataclass(frozen=True)
class IndexEnsureCompleted:
    """An index initialization check, optionally including a completed full sync."""

    root: str
    result: object | None


@dataclass(frozen=True)
class IndexWriteCompleted:
    """A committed incremental index write."""

    root: str
    operation: IndexOperationKind


@dataclass(frozen=True)
class IndexWriteFailed:
    """A failed index operation; later queued work remains eligible to run."""

    root: str
    operation: IndexOperationKind
    error: str


@dataclass(frozen=True)
class IndexRefreshRequest:
    """Identity for one user-visible or automatic index refresh."""

    kind: IndexRefreshKind
    request_id: int
    workspace_generation: int
    root: str
    query: str | None = None
    path: str | None = None


@dataclass(frozen=True)
class IndexRefreshCompleted:
    """An eligible index refresh; ``result`` is ``None`` when already fresh."""

    request: IndexRefreshRequest
    result: object | None


@dataclass(frozen=True)
class IndexRefreshProgress:
    """One committed refresh chunk; later root writes may run before the next one."""

    request: IndexRefreshRequest
    result: object


@dataclass(frozen=True)
class IndexRefreshFailed:
    """A failed freshness check or full refresh."""

    request: IndexRefreshRequest
    error: str


@dataclass(frozen=True)
class IndexStaleResultEvicted:
    """The exact missing path was removed before local reconciliation."""

    request: IndexRefreshRequest


@dataclass(frozen=True)
class IndexReadRequest:
    """Identity for an independently scheduled index read."""

    kind: IndexReadKind
    request_id: int
    workspace_generation: int
    root: str
    query: str | None = None
    candidate_paths: tuple[str, ...] = ()


@dataclass(frozen=True)
class IndexSearchCompleted:
    request: IndexReadRequest
    paths: tuple[str, ...]


@dataclass(frozen=True)
class IptcEmptyIndexCompleted:
    request: IndexReadRequest
    result: object


@dataclass(frozen=True)
class KnownTagsCompleted:
    request: IndexReadRequest
    tags: frozenset[str]


@dataclass(frozen=True)
class IndexReadFailed:
    request: IndexReadRequest
    error: str


DiscoveryEvent: TypeAlias = DiscoveryCompleted | DiscoveryFailed
IndexEvent: TypeAlias = (
    IndexEnsureCompleted
    | IndexWriteCompleted
    | IndexWriteFailed
    | IndexRefreshCompleted
    | IndexRefreshProgress
    | IndexRefreshFailed
    | IndexStaleResultEvicted
    | IndexSearchCompleted
    | IptcEmptyIndexCompleted
    | KnownTagsCompleted
    | IndexReadFailed
)
CoordinatorEvent: TypeAlias = DiscoveryEvent | IndexEvent


@dataclass(frozen=True)
class _IndexOperation:
    kind: IndexOperationKind
    paths: tuple[str, ...] = ()
    refresh_request: IndexRefreshRequest | None = None
    restart: bool = False


@dataclass
class _RootWriteQueue:
    pending: list[_IndexOperation] = field(default_factory=list)
    pending_states: dict[str, object] = field(default_factory=dict)
    update_scheduled: bool = False
    cancel_requested: bool = False
    running: bool = False


def _normalize_path(path: str | Path) -> str:
    try:
        return str(Path(path).resolve())
    except OSError:
        return str(Path(path))


class BackgroundCoordinator:
    """Own background discovery and serial index writes behind one deep seam.

    Replacement discovery starts a new workspace generation immediately. Additive
    discoveries belong to the current generation and are released in the order
    their drops began, independent of completion order. Every index root has one
    serial write queue; pending confirmed states coalesce by normalized photo path.
    """

    def __init__(
        self,
        *,
        discovery: DiscoveryAdapter,
        index: IndexAdapter,
        runner: BackgroundRunner,
        event_sink: Callable[[CoordinatorEvent], None],
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
        self._index_queues: dict[str, _RootWriteQueue] = {}
        self._next_index_refresh_request_id = 0
        self._stale_result_repair_roots: set[str] = set()
        self._next_index_read_request_id = 0
        self._current_search_request_id: int | None = None
        self._current_iptc_empty_request_id: int | None = None
        self._current_known_tags_request_id: int | None = None

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
        self._schedule_discovery(request)
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
        self._schedule_discovery(request)
        return request

    def ensure_index(
        self,
        root: str | Path,
        paths: Iterable[str | Path],
        *,
        paths_are_normalized: bool = False,
    ) -> None:
        """Check and, when needed, fully synchronize one discovered path set."""
        normalized_paths = (
            tuple(str(path) for path in paths)
            if paths_are_normalized
            else tuple(_normalize_path(path) for path in paths)
        )
        self._enqueue_index_operation(
            _normalize_path(root),
            _IndexOperation(IndexOperationKind.ENSURE, normalized_paths),
        )

    def index_missing_paths(
        self, root: str | Path, paths: Iterable[str | Path]
    ) -> None:
        """Index paths that were added after an already initialized index."""
        self._enqueue_index_operation(
            _normalize_path(root),
            _IndexOperation(
                IndexOperationKind.INDEX_MISSING,
                tuple(_normalize_path(path) for path in paths),
            ),
        )

    def refresh_if_stale(
        self, root: str | Path, *, workspace_generation: int
    ) -> IndexRefreshRequest:
        """Queue one full refresh only when the root's metadata is stale."""
        request = self._new_index_refresh_request(
            IndexRefreshKind.AUTOMATIC, root, workspace_generation
        )
        self._enqueue_index_operation(
            request.root,
            _IndexOperation(
                IndexOperationKind.REFRESH_IF_STALE, refresh_request=request
            ),
        )
        return request

    def reindex(
        self, root: str | Path, *, workspace_generation: int
    ) -> IndexRefreshRequest:
        """Queue a user-requested full root refresh behind existing writes."""
        request = self._new_index_refresh_request(
            IndexRefreshKind.MANUAL, root, workspace_generation
        )
        self._enqueue_index_operation(
            request.root,
            _IndexOperation(
                IndexOperationKind.FULL_REINDEX,
                refresh_request=request,
                restart=True,
            ),
        )
        return request

    def cancel_refresh(self, root: str | Path) -> None:
        """Cancel a refresh at its next chunk boundary and drop its checkpoint."""
        normalized_root = _normalize_path(root)
        with self._lock:
            queue = self._index_queues.setdefault(normalized_root, _RootWriteQueue())
            # Cancellation must beat a refresh continuation but cannot interrupt
            # the ExifTool subgroup currently owned by a worker.
            queue.cancel_requested = True
            queue.pending = [
                operation
                for operation in queue.pending
                if operation.kind
                not in {
                    IndexOperationKind.ENSURE,
                    IndexOperationKind.REFRESH_IF_STALE,
                    IndexOperationKind.FULL_REINDEX,
                }
            ]
            queue.pending.insert(0, _IndexOperation(IndexOperationKind.CANCEL_REFRESH))
            work = self._next_index_work_locked(normalized_root, queue)
        if work is not None:
            self._runner.submit(work)

    def repair_stale_search_result(
        self,
        root: str | Path,
        path: str | Path,
        *,
        workspace_generation: int,
        query: str,
    ) -> IndexRefreshRequest | None:
        """Queue one deduplicated full repair after a stale search result.

        Repairs remain queued for index integrity after the originating workspace
        becomes obsolete. Callers receive ``None`` when this root already has a
        repair pending or running.
        """
        normalized_root = _normalize_path(root)
        with self._lock:
            if normalized_root in self._stale_result_repair_roots:
                return None
            self._stale_result_repair_roots.add(normalized_root)
            request = self._new_index_refresh_request_locked(
                IndexRefreshKind.STALE_RESULT_REPAIR,
                normalized_root,
                workspace_generation,
                query,
                _normalize_path(path),
            )
            queue = self._index_queues.setdefault(normalized_root, _RootWriteQueue())
            queue.pending.append(
                _IndexOperation(
                    IndexOperationKind.FULL_REINDEX,
                    refresh_request=request,
                    restart=True,
                )
            )
            work = self._next_index_work_locked(normalized_root, queue)
        if work is not None:
            self._runner.submit(work)
        return request

    def submit_confirmed_states(
        self, root: str | Path, states: Mapping[str, object]
    ) -> None:
        """Queue newest confirmed metadata per path after any older root write."""
        if not states:
            return
        normalized_root = _normalize_path(root)
        normalized_states = {
            _normalize_path(path): state for path, state in states.items()
        }
        with self._lock:
            queue = self._index_queues.setdefault(normalized_root, _RootWriteQueue())
            queue.pending_states.update(normalized_states)
            if not queue.update_scheduled:
                queue.pending.append(_IndexOperation(IndexOperationKind.UPDATE_STATES))
                queue.update_scheduled = True
            work = self._next_index_work_locked(normalized_root, queue)
        if work is not None:
            self._runner.submit(work)

    def search_index(
        self, root: str | Path, query: str, *, workspace_generation: int
    ) -> IndexReadRequest:
        """Read search matches in the background, superseding older searches."""
        request = self._new_index_read_request(
            IndexReadKind.SEARCH, root, workspace_generation, query
        )
        with self._lock:
            self._current_search_request_id = request.request_id

        def read() -> None:
            self._run_index_read(request)

        self._runner.submit(read)
        return request

    def load_iptc_empty(
        self,
        root: str | Path,
        candidate_paths: Sequence[str | Path],
        *,
        workspace_generation: int,
    ) -> IndexReadRequest:
        """Read workspace-scoped IPTC-empty candidates, superseding older reads."""
        request = self._new_index_read_request(
            IndexReadKind.IPTC_EMPTY,
            root,
            workspace_generation,
            candidate_paths=tuple(_normalize_path(path) for path in candidate_paths),
        )
        with self._lock:
            self._current_iptc_empty_request_id = request.request_id

        def read() -> None:
            self._run_index_read(request)

        self._runner.submit(read)
        return request

    def load_known_tags(
        self, root: str | Path, *, workspace_generation: int
    ) -> IndexReadRequest:
        """Read a known-tag snapshot in the background, superseding older reads."""
        request = self._new_index_read_request(
            IndexReadKind.KNOWN_TAGS, root, workspace_generation
        )
        with self._lock:
            self._current_known_tags_request_id = request.request_id

        def read() -> None:
            self._run_index_read(request)

        self._runner.submit(read)
        return request

    def invalidate_search(self) -> None:
        """Prevent an already-running search completion from being UI-eligible."""
        with self._lock:
            self._current_search_request_id = None

    def invalidate_iptc_empty(self) -> None:
        """Prevent an already-running IPTC-empty read from being UI-eligible."""
        with self._lock:
            self._current_iptc_empty_request_id = None

    def invalidate_known_tags(self) -> None:
        """Prevent an already-running known-tag completion from being UI-eligible."""
        with self._lock:
            self._current_known_tags_request_id = None

    def _new_index_refresh_request(
        self,
        kind: IndexRefreshKind,
        root: str | Path,
        workspace_generation: int,
    ) -> IndexRefreshRequest:
        with self._lock:
            return self._new_index_refresh_request_locked(
                kind, root, workspace_generation
            )

    def _new_index_refresh_request_locked(
        self,
        kind: IndexRefreshKind,
        root: str | Path,
        workspace_generation: int,
        query: str | None = None,
        path: str | None = None,
    ) -> IndexRefreshRequest:
        request_id = self._next_index_refresh_request_id
        self._next_index_refresh_request_id += 1
        return IndexRefreshRequest(
            kind=kind,
            request_id=request_id,
            workspace_generation=workspace_generation,
            root=_normalize_path(root),
            query=query,
            path=path,
        )

    def _new_index_read_request(
        self,
        kind: IndexReadKind,
        root: str | Path,
        workspace_generation: int,
        query: str | None = None,
        candidate_paths: tuple[str, ...] = (),
    ) -> IndexReadRequest:
        with self._lock:
            request_id = self._next_index_read_request_id
            self._next_index_read_request_id += 1
        return IndexReadRequest(
            kind=kind,
            request_id=request_id,
            workspace_generation=workspace_generation,
            root=_normalize_path(root),
            query=query,
            candidate_paths=candidate_paths,
        )

    def _new_request_id(self) -> int:
        request_id = self._next_request_id
        self._next_request_id += 1
        return request_id

    def _schedule_discovery(self, request: DiscoveryRequest) -> None:
        def work() -> None:
            try:
                paths = tuple(
                    sorted(
                        (
                            _normalize_path(path)
                            for path in self._discovery.discover(request.root)
                        ),
                        key=str.casefold,
                    )
                )
            except Exception as error:  # noqa: BLE001 - worker boundary reports failures
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
            self._accept_discovery(event)

        self._runner.submit(work)

    def _accept_discovery(self, event: DiscoveryEvent) -> None:
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

    def _run_index_read(self, request: IndexReadRequest) -> None:
        try:
            if request.kind is IndexReadKind.SEARCH:
                paths = self._index.search(request.root, request.query or "")
                event: IndexEvent = IndexSearchCompleted(request, tuple(paths))
            elif request.kind is IndexReadKind.IPTC_EMPTY:
                event = IptcEmptyIndexCompleted(
                    request,
                    self._index.load_iptc_empty(request.root, request.candidate_paths),
                )
            else:
                event = KnownTagsCompleted(
                    request, frozenset(self._index.load_known_tags(request.root))
                )
        except Exception as error:  # noqa: BLE001 - worker boundary reports failures
            event = IndexReadFailed(request, str(error))
        self._accept_index_read(event)

    def _accept_index_read(
        self,
        event: IptcEmptyIndexCompleted
        | IndexSearchCompleted
        | KnownTagsCompleted
        | IndexReadFailed,
    ) -> None:
        request = event.request
        with self._lock:
            current_id = {
                IndexReadKind.SEARCH: self._current_search_request_id,
                IndexReadKind.IPTC_EMPTY: self._current_iptc_empty_request_id,
                IndexReadKind.KNOWN_TAGS: self._current_known_tags_request_id,
            }[request.kind]
            if request.request_id != current_id:
                return
        self._event_sink(event)

    def _enqueue_index_operation(self, root: str, operation: _IndexOperation) -> None:
        with self._lock:
            queue = self._index_queues.setdefault(root, _RootWriteQueue())
            queue.pending.append(operation)
            work = self._next_index_work_locked(root, queue)
        if work is not None:
            self._runner.submit(work)

    def _next_index_work_locked(
        self, root: str, queue: _RootWriteQueue
    ) -> Callable[[], None] | None:
        if queue.running or not queue.pending:
            return None
        operation = queue.pending.pop(0)
        queue.running = True
        return lambda: self._run_index_operation(root, operation)

    def _run_index_operation(self, root: str, operation: _IndexOperation) -> None:
        with self._lock:
            cancel_refresh = (
                operation.kind
                in {
                    IndexOperationKind.ENSURE,
                    IndexOperationKind.REFRESH_IF_STALE,
                    IndexOperationKind.FULL_REINDEX,
                }
                and self._index_queues[root].cancel_requested
            )
        if cancel_refresh:
            # The queued CANCEL_REFRESH operation owns checkpoint cleanup. This
            # continuation must not start another ExifTool subgroup before it runs.
            self._complete_index_operation(
                root,
                IndexWriteCompleted(root, IndexOperationKind.CANCEL_REFRESH),
                operation,
            )
            return
        try:
            if operation.kind is IndexOperationKind.ENSURE:
                if self._index.is_initialized(root):
                    result = None
                elif self._index.needs_keyword_index_rebuild(root):
                    result = self._index.refresh(root)
                else:
                    result = self._index.sync(root, operation.paths)
                event: IndexEvent = IndexEnsureCompleted(root, result)
            elif operation.kind in {
                IndexOperationKind.REFRESH_IF_STALE,
                IndexOperationKind.FULL_REINDEX,
            }:
                request = operation.refresh_request
                if request is None:
                    raise RuntimeError("Index refresh operation has no request")
                should_refresh = (
                    operation.kind is IndexOperationKind.FULL_REINDEX
                    or self._index.is_refresh_stale(root)
                )
                if request.kind is IndexRefreshKind.STALE_RESULT_REPAIR:
                    if request.path is None:
                        raise RuntimeError("Stale-result repair has no missing path")
                    self._index.remove_photo(root, request.path)
                    self._event_sink(IndexStaleResultEvicted(request))
                    result = self._index.reconcile_directory(
                        root, str(Path(request.path).parent)
                    )
                else:
                    if not should_refresh:
                        result = None
                    elif operation.restart and hasattr(self._index, "restart_refresh"):
                        result = self._index.restart_refresh(root)
                    else:
                        result = self._index.refresh(root)
                if result is not None and getattr(result, "complete", True) is False:
                    event = IndexRefreshProgress(request, result)
                else:
                    event = IndexRefreshCompleted(request, result)
            elif operation.kind is IndexOperationKind.CANCEL_REFRESH:
                if hasattr(self._index, "cancel_refresh"):
                    self._index.cancel_refresh(root)
                event = IndexWriteCompleted(root, operation.kind)
            elif operation.kind is IndexOperationKind.INDEX_MISSING:
                self._index.index_missing(root, operation.paths)
                event = IndexWriteCompleted(root, operation.kind)
            else:
                states = self._take_pending_states(root)
                if states:
                    self._index.update_states(root, states)
                event = IndexWriteCompleted(root, operation.kind)
        except Exception as error:  # noqa: BLE001 - worker boundary reports failures
            if operation.refresh_request is not None:
                event = IndexRefreshFailed(operation.refresh_request, str(error))
            else:
                event = IndexWriteFailed(root, operation.kind, str(error))
        self._complete_index_operation(root, event, operation)

    def _take_pending_states(self, root: str) -> dict[str, object]:
        with self._lock:
            queue = self._index_queues[root]
            states = queue.pending_states
            queue.pending_states = {}
            queue.update_scheduled = False
            return states

    def _complete_index_operation(
        self, root: str, event: IndexEvent, operation: _IndexOperation
    ) -> None:
        with self._lock:
            if (
                isinstance(event, (IndexRefreshCompleted, IndexRefreshFailed))
                and event.request.kind is IndexRefreshKind.STALE_RESULT_REPAIR
            ):
                self._stale_result_repair_roots.discard(root)
            queue = self._index_queues[root]
            queue.running = False
            incomplete_refresh = isinstance(event, IndexRefreshProgress) or (
                isinstance(event, IndexEnsureCompleted)
                and event.result is not None
                and getattr(event.result, "complete", True) is False
            )
            if incomplete_refresh and not queue.cancel_requested:
                # Append after pending writes so confirmed mutations are committed
                # before the next older refresh chunk can overwrite their index row.
                queue.pending.append(
                    _IndexOperation(
                        operation.kind,
                        operation.paths,
                        operation.refresh_request,
                        restart=False,
                    )
                )
            if operation.kind is IndexOperationKind.CANCEL_REFRESH:
                queue.cancel_requested = False
            work = self._next_index_work_locked(root, queue)
        self._event_sink(event)
        if work is not None:
            self._runner.submit(work)
