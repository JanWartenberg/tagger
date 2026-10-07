"""Qt-free duplicate-candidate detection models and implementations."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
from pathlib import Path
from threading import Event, Lock
from typing import Protocol

from tagger_app.exif_tool import ExifTool, KeywordState
from tagger_app.utils import normalize_path


@dataclass(frozen=True)
class ScanRequest:
    """The immutable scope captured for one detector run."""

    scan_id: str
    paths: tuple[str, ...]

    def __post_init__(self) -> None:
        normalized = tuple(sorted({normalize_path(path) for path in self.paths}))
        object.__setattr__(self, "paths", normalized)
        if not self.scan_id:
            raise ValueError("scan_id must not be empty")


@dataclass(frozen=True)
class PhotoMetadata:
    """The capture fields and canonical tags needed by duplicate review."""

    date_original: str | None = None
    date_create: str | None = None
    iptc_tags: tuple[str, ...] = ()
    iptc_readable: bool = True


@dataclass(frozen=True)
class MetadataReadError:
    message: str


@dataclass(frozen=True)
class CandidateMember:
    path: str
    timestamp: str
    source_field: str
    iptc_tags: tuple[str, ...] = ()
    iptc_readable: bool = True


@dataclass(frozen=True)
class CandidateGroup:
    group_id: str
    members: tuple[CandidateMember, ...]


@dataclass(frozen=True)
class ScanProgress:
    processed: int
    total: int


@dataclass(frozen=True)
class PhotoScanError:
    path: str
    message: str


@dataclass(frozen=True)
class ScanResult:
    scan_id: str
    detector_id: str
    groups: tuple[CandidateGroup, ...]
    errors: tuple[PhotoScanError, ...]
    timestampless_paths: tuple[str, ...]
    processed: int
    total: int
    complete: bool


class DuplicateScopeKind(str, Enum):
    INDEX_DATABASE = "index-database"
    SUBFOLDER = "subfolder"


@dataclass(frozen=True)
class ScopePreparationRequest:
    request_id: int
    kind: DuplicateScopeKind
    root: str


@dataclass(frozen=True)
class DuplicateScopeSnapshot:
    """An immutable path scope prepared before an explicit detector run."""

    scope_id: str
    kind: DuplicateScopeKind
    root: str
    paths: tuple[str, ...]

    def __post_init__(self) -> None:
        normalized = tuple(sorted({normalize_path(path) for path in self.paths}))
        object.__setattr__(self, "root", normalize_path(self.root))
        object.__setattr__(self, "paths", normalized)


@dataclass(frozen=True)
class ScopePreparationCompleted:
    request: ScopePreparationRequest
    snapshot: DuplicateScopeSnapshot


@dataclass(frozen=True)
class ScopePreparationFailed:
    request: ScopePreparationRequest
    error: str


class ScopePreparationRunner(Protocol):
    def submit(self, work: Callable[[], None]) -> None: ...


@dataclass(frozen=True)
class DuplicateScanStarted:
    request: ScanRequest
    detector_id: str


@dataclass(frozen=True)
class DuplicateScanProgress:
    request: ScanRequest
    detector_id: str
    progress: ScanProgress


@dataclass(frozen=True)
class DuplicateScanCompleted:
    request: ScanRequest
    result: ScanResult
    ignored_identities: frozenset[str] = frozenset()


@dataclass(frozen=True)
class DuplicateScanFailed:
    request: ScanRequest
    detector_id: str
    error: str


DuplicateScanEvent = (
    DuplicateScanStarted
    | DuplicateScanProgress
    | DuplicateScanCompleted
    | DuplicateScanFailed
)


class DuplicateScanCoordinator:
    """Run one current detector scan and suppress cancelled or stale events."""

    def __init__(
        self,
        *,
        reader: CaptureMetadataReader,
        runner: ScopePreparationRunner,
        event_sink: Callable[[DuplicateScanEvent], None],
    ) -> None:
        self._reader = reader
        self._runner = runner
        self._event_sink = event_sink
        self._lock = Lock()
        self._next_scan_id = 0
        self._current_scan_id: str | None = None
        self._cancel_event: Event | None = None

    def start(
        self,
        snapshot: DuplicateScopeSnapshot,
        detector: DuplicateCandidateDetector,
        *,
        load_ignored: Callable[[], frozenset[str]] | None = None,
    ) -> ScanRequest:
        with self._lock:
            if self._cancel_event is not None:
                self._cancel_event.set()
            self._next_scan_id += 1
            request = ScanRequest(
                f"{snapshot.scope_id}-scan-{self._next_scan_id}", snapshot.paths
            )
            cancel_event = Event()
            self._cancel_event = cancel_event
            self._current_scan_id = request.scan_id

        self._event_sink(DuplicateScanStarted(request, detector.detector_id))

        def publish(event: DuplicateScanEvent) -> None:
            with self._lock:
                if self._current_scan_id != request.scan_id:
                    return
            self._event_sink(event)

        def work() -> None:
            try:
                result = detector.scan(
                    request,
                    self._reader,
                    on_progress=lambda progress: publish(
                        DuplicateScanProgress(request, detector.detector_id, progress)
                    ),
                    is_cancelled=cancel_event.is_set,
                )
                ignored = (
                    load_ignored()
                    if load_ignored and not cancel_event.is_set()
                    else frozenset()
                )
            except Exception as error:  # noqa: BLE001 - worker reports failures
                publish(
                    DuplicateScanFailed(
                        request,
                        detector.detector_id,
                        str(error) or "duplicate scan failed",
                    )
                )
                return
            if result.complete and not cancel_event.is_set():
                publish(DuplicateScanCompleted(request, result, ignored))

        self._runner.submit(work)
        return request

    def cancel(self) -> None:
        with self._lock:
            if self._cancel_event is not None:
                self._cancel_event.set()
            self._current_scan_id = None
            self._cancel_event = None


class DuplicateScopeCoordinator:
    """Prepare one current immutable scope without publishing stale work."""

    def __init__(
        self,
        *,
        discovery: object,
        index_factory: Callable[[str], object],
        runner: ScopePreparationRunner,
        event_sink: Callable[
            [ScopePreparationCompleted | ScopePreparationFailed], None
        ],
    ) -> None:
        self._discovery = discovery
        self._index_factory = index_factory
        self._runner = runner
        self._event_sink = event_sink
        self._lock = Lock()
        self._next_request_id = 0
        self._current_request_id: int | None = None

    def prepare_index(self, root: str | Path) -> ScopePreparationRequest:
        return self._prepare(DuplicateScopeKind.INDEX_DATABASE, root)

    def prepare_subfolder(self, root: str | Path) -> ScopePreparationRequest:
        return self._prepare(DuplicateScopeKind.SUBFOLDER, root)

    def prepare_discovered_subfolder(
        self, root: str | Path, paths: Sequence[str]
    ) -> ScopePreparationRequest:
        """Freeze paths already returned by the shared folder discovery flow."""
        return self._prepare(DuplicateScopeKind.SUBFOLDER, root, paths=tuple(paths))

    def invalidate(self) -> None:
        """Prevent active work from publishing after the scope choice changes."""
        with self._lock:
            self._current_request_id = None

    def _prepare(
        self,
        kind: DuplicateScopeKind,
        root: str | Path,
        *,
        paths: tuple[str, ...] | None = None,
    ) -> ScopePreparationRequest:
        with self._lock:
            self._next_request_id += 1
            request = ScopePreparationRequest(
                self._next_request_id, kind, normalize_path(root)
            )
            self._current_request_id = request.request_id

        def work() -> None:
            try:
                if paths is not None:
                    scan_request = ScanRequest(f"scope-{request.request_id}", paths)
                elif request.kind is DuplicateScopeKind.INDEX_DATABASE:
                    scan_request = IndexedPhotoScope(
                        self._index_factory(request.root)
                    ).snapshot(f"scope-{request.request_id}")
                else:
                    scan_request = SubfolderPhotoScope(self._discovery).snapshot(
                        f"scope-{request.request_id}", request.root
                    )
                event: ScopePreparationCompleted | ScopePreparationFailed = (
                    ScopePreparationCompleted(
                        request,
                        DuplicateScopeSnapshot(
                            scan_request.scan_id,
                            request.kind,
                            request.root,
                            scan_request.paths,
                        ),
                    )
                )
            except Exception as error:  # noqa: BLE001 - worker reports failures
                event = ScopePreparationFailed(
                    request, str(error) or "scope preparation failed"
                )
            with self._lock:
                if self._current_request_id != request.request_id:
                    return
            self._event_sink(event)

        self._runner.submit(work)
        return request


class CaptureMetadataReader(Protocol):
    def read_many(
        self, paths: Sequence[str]
    ) -> Mapping[str, PhotoMetadata | MetadataReadError | Exception]: ...


class ExifToolCaptureMetadataReader:
    """Adapt ExifTool's keyword reader to the detector's narrow seam."""

    def __init__(self, exif: ExifTool | None = None) -> None:
        self._exif = exif or ExifTool()

    def read_many(
        self, paths: Sequence[str]
    ) -> Mapping[str, PhotoMetadata | MetadataReadError]:
        normalized = [normalize_path(path) for path in paths]
        try:
            states = self._exif.read_keywords_many(normalized)
        except Exception as error:  # noqa: BLE001 - report batch failures per photo
            return {
                path: MetadataReadError(str(error) or "metadata read failed")
                for path in normalized
            }

        records: dict[str, PhotoMetadata | MetadataReadError] = {}
        for path in normalized:
            state = states.get(path)
            if state is None:
                records[path] = MetadataReadError("metadata record unavailable")
            else:
                records[path] = _metadata_from_keyword_state(state)
        return records


def _metadata_from_keyword_state(state: KeywordState) -> PhotoMetadata:
    return PhotoMetadata(
        state.date_original,
        state.date_create,
        tuple(state.iptc),
        state.iptc_readable,
    )


class DuplicateCandidateDetector(Protocol):
    detector_id: str
    display_name: str

    def scan(
        self,
        request: ScanRequest,
        reader: CaptureMetadataReader,
        *,
        batch_size: int = 200,
        on_progress: Callable[[ScanProgress], None] | None = None,
        is_cancelled: Callable[[], bool] | None = None,
    ) -> ScanResult: ...


class SameCaptureTimestampDetector:
    """Find candidate groups whose effective capture timestamp is identical."""

    detector_id = "same-capture-timestamp"
    display_name = "Same capture timestamp"

    def scan(
        self,
        request: ScanRequest,
        reader: CaptureMetadataReader,
        *,
        batch_size: int = 200,
        on_progress: Callable[[ScanProgress], None] | None = None,
        is_cancelled: Callable[[], bool] | None = None,
    ) -> ScanResult:
        if batch_size < 1:
            raise ValueError("batch_size must be positive")

        total = len(request.paths)
        processed = 0
        errors: list[PhotoScanError] = []
        if total == 0 and on_progress is not None:
            on_progress(ScanProgress(0, 0))
        timestampless_paths: list[str] = []
        by_timestamp: dict[str, list[CandidateMember]] = {}

        for start in range(0, total, batch_size):
            if is_cancelled is not None and is_cancelled():
                return _cancelled_result(
                    request, errors, timestampless_paths, processed, total
                )

            batch = request.paths[start : start + batch_size]
            records = reader.read_many(batch)
            for path in batch:
                record = records.get(path)
                if isinstance(record, Exception):
                    errors.append(
                        PhotoScanError(path, str(record) or "metadata read failed")
                    )
                    continue
                if record is None:
                    errors.append(PhotoScanError(path, "metadata record unavailable"))
                    continue
                if isinstance(record, MetadataReadError):
                    errors.append(PhotoScanError(path, record.message))
                    continue

                timestamp, source_field = _effective_timestamp(record)
                if timestamp is not None:
                    by_timestamp.setdefault(timestamp, []).append(
                        CandidateMember(
                            path,
                            timestamp,
                            source_field,
                            record.iptc_tags,
                            record.iptc_readable,
                        )
                    )
                else:
                    timestampless_paths.append(path)
            processed += len(batch)
            if on_progress is not None:
                on_progress(ScanProgress(processed, total))

        groups = tuple(
            _make_group(timestamp, members)
            for timestamp, members in sorted(by_timestamp.items())
            if len(members) >= 2
        )
        return ScanResult(
            request.scan_id,
            self.detector_id,
            groups,
            tuple(sorted(errors, key=lambda error: error.path)),
            tuple(timestampless_paths),
            processed,
            total,
            True,
        )


def _effective_timestamp(metadata: PhotoMetadata) -> tuple[str | None, str]:
    date_original = _usable_timestamp(metadata.date_original)
    if date_original is not None:
        return date_original, "EXIF:DateTimeOriginal"
    date_create = _usable_timestamp(metadata.date_create)
    if date_create is not None:
        return date_create, "EXIF:CreateDate"
    return None, ""


def _usable_timestamp(value: str | None) -> str | None:
    if value is None or not (timestamp := value.strip()):
        return None
    digits = [character for character in timestamp if character.isdigit()]
    if digits and all(digit == "0" for digit in digits):
        return None
    return timestamp


def _make_group(timestamp: str, members: list[CandidateMember]) -> CandidateGroup:
    ordered = tuple(sorted(members, key=lambda member: member.path))
    digest = sha256(
        (timestamp + "\0" + "\0".join(member.path for member in ordered)).encode()
    ).hexdigest()[:16]
    return CandidateGroup(
        f"{SameCaptureTimestampDetector.detector_id}:{digest}", ordered
    )


def _cancelled_result(
    request: ScanRequest,
    errors: list[PhotoScanError],
    timestampless_paths: list[str],
    processed: int,
    total: int,
) -> ScanResult:
    return ScanResult(
        request.scan_id,
        SameCaptureTimestampDetector.detector_id,
        (),
        tuple(sorted(errors, key=lambda error: error.path)),
        tuple(timestampless_paths),
        processed,
        total,
        False,
    )


class IndexedPhotoScope:
    """Snapshot every indexed path without exposing the index connection."""

    def __init__(self, index: object) -> None:
        self._index = index

    def snapshot(self, scan_id: str) -> ScanRequest:
        paths = self._index.snapshot_photo_paths()
        return ScanRequest(scan_id, tuple(paths))


class SubfolderPhotoScope:
    """Snapshot supported files below one selected directory."""

    def __init__(self, discovery: object) -> None:
        self._discovery = discovery

    def snapshot(self, scan_id: str, root: str | Path) -> ScanRequest:
        paths = self._discovery.discover(str(root))
        return ScanRequest(scan_id, tuple(paths))
