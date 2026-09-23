"""Qt-free duplicate-candidate detection models and implementations."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Protocol

from exif_tool import ExifTool, KeywordState
from utils import normalize_path


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
    """The capture fields needed by the initial detector."""

    date_original: str | None = None
    date_create: str | None = None


@dataclass(frozen=True)
class MetadataReadError:
    message: str


@dataclass(frozen=True)
class CandidateMember:
    path: str
    timestamp: str
    source_field: str


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
    return PhotoMetadata(state.date_original, state.date_create)


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
                        CandidateMember(path, timestamp, source_field)
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
    if metadata.date_original is not None and metadata.date_original.strip():
        return metadata.date_original.strip(), "EXIF:DateTimeOriginal"
    if metadata.date_create is not None and metadata.date_create.strip():
        return metadata.date_create.strip(), "EXIF:CreateDate"
    return None, ""


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
