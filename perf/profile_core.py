"""External profiling harness for TAGGER's non-Qt core workflows.

The application is imported as a library, but no production files are modified:
all photo files and the SQLite index are created below a temporary directory.
Use ``--profile-out`` to write a cProfile report and ``--json-out`` for results.
"""

from __future__ import annotations

import argparse
import cProfile
import io
import json
import os
import pstats
import sys
import tempfile
import time
import tracemalloc
from collections import Counter
from collections.abc import Callable
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import exif_tool as exif_tool_module
import indexing as indexing_module
from exif_tool import KeywordState
from indexing import IndexRefreshProgress, PhotoIndex
from photo_workspace import PhotoWorkspace
from services.photo_discovery import FileSystemPhotoDiscovery
from utils import normalize_path


class SyntheticExifTool:
    """Deterministic ExifTool substitute for measuring TAGGER's core overhead."""

    def __init__(self) -> None:
        self.calls = 0
        self.files = 0

    def read_keywords_many(self, file_paths: list[str]) -> dict[str, KeywordState]:
        self.calls += 1
        self.files += len(file_paths)
        return {
            normalize_path(path): KeywordState(
                ["synthetic"],
                ["synthetic"],
                date_original="2024:01:01 12:00:00",
            )
            for path in file_paths
        }


def _make_fixture(root: Path, photo_count: int, depth: int) -> list[str]:
    paths: list[str] = []
    for index in range(photo_count):
        directory = (
            root / f"level-{index % max(depth, 1):03d}" / f"group-{index % 17:02d}"
        )
        directory.mkdir(parents=True, exist_ok=True)
        suffix = ".jpeg" if index % 2 else ".jpg"
        path = directory / f"photo-{index:06d}{suffix}"
        path.write_bytes(b"synthetic photo payload")
        paths.append(str(path))
    return paths


class TracedPhotoIndex(PhotoIndex):
    """PhotoIndex with operation counters and timings owned by the harness."""

    def __init__(
        self,
        root: str | Path,
        counters: Counter[str],
        timings: Counter[str] | None = None,
    ) -> None:
        super().__init__(root)
        self._counters = counters
        self._timings = timings if timings is not None else Counter()

    def _connect(self):  # type: ignore[no-untyped-def]
        connection = super()._connect()
        connection.set_trace_callback(
            lambda statement: self._counters.update(sqlite_statements=1)
        )
        return connection

    def _take_refresh_path_batch(self, conn):  # type: ignore[no-untyped-def]
        started = time.perf_counter()
        result = super()._take_refresh_path_batch(conn)
        self._timings["queue_batch_seconds"] += time.perf_counter() - started
        return result

    def _index_refresh_paths(self, conn, exif, paths):  # type: ignore[no-untyped-def]
        started = time.perf_counter()
        result = super()._index_refresh_paths(conn, exif, paths)
        self._timings["metadata_batch_seconds"] += time.perf_counter() - started
        return result

    def _sync_paths(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        started = time.perf_counter()
        result = super()._sync_paths(*args, **kwargs)
        self._timings["reconciliation_seconds"] += time.perf_counter() - started
        return result


def _run_refresh(
    index: TracedPhotoIndex, exif: SyntheticExifTool
) -> tuple[object, list[dict[str, object]]]:
    steps: list[dict[str, object]] = []
    while True:
        started = time.perf_counter()
        result = index.refresh_step(exif)
        phase = (
            result.phase
            if isinstance(result, IndexRefreshProgress)
            else "reconciliation"
        )
        steps.append(
            {
                "phase": phase,
                "elapsed_seconds": time.perf_counter() - started,
            }
        )
        if not isinstance(result, IndexRefreshProgress):
            return result, steps


def _prepare_refresh(root: Path, counters: Counter[str], paths: list[str]) -> None:
    """Build the refresh fixture outside the profiled refresh operation."""
    exif = SyntheticExifTool()
    index = TracedPhotoIndex(root, counters)
    index.sync_paths(exif, paths, force=True)


def _run_scenario(
    name: str, root: Path, paths: list[str], counters: Counter[str]
) -> dict:
    exif = SyntheticExifTool()
    discovery = FileSystemPhotoDiscovery()
    internal_timings: Counter[str] = Counter()
    index = TracedPhotoIndex(root, counters, internal_timings)
    started = time.perf_counter()

    if name == "discovery":
        discovered = discovery.discover(str(root))
        counters.update(discovered=len(discovered))
    elif name == "sync":
        discovered = discovery.discover(str(root))
        result = index.sync_paths(exif, discovered, force=True)
        counters.update(discovered=len(discovered), indexed=result.updated_count)
    elif name == "refresh":
        result, refresh_steps = _run_refresh(index, exif)
        counters.update(discovered=len(paths), indexed=result.updated_count)
    elif name == "workspace":
        workspace = PhotoWorkspace()
        workspace.add_paths(paths)
        workspace.set_filename_filter("photo-000")
        snapshot = workspace.snapshot()
        counters.update(
            workspace_paths=len(snapshot.paths),
            visible_paths=len(snapshot.visible_paths),
        )
    else:
        raise ValueError(f"Unknown scenario: {name}")

    return {
        "scenario": name,
        "elapsed_seconds": time.perf_counter() - started,
        "exiftool_calls": exif.calls,
        "exiftool_files": exif.files,
        "counters": dict(counters),
        **(
            {
                "refresh_steps": refresh_steps,
                "refresh_internal_timings": dict(internal_timings),
            }
            if name == "refresh"
            else {}
        ),
    }


def _install_normalization_trace(counters: Counter[str]) -> Callable[[], None]:
    """Count normalization calls by owning module without changing their result."""
    originals = {
        "indexing": indexing_module.normalize_path,
        "exif_tool": exif_tool_module.normalize_path,
    }
    for owner, original in originals.items():

        def traced(path, *, _owner=owner, _original=original):  # type: ignore[no-untyped-def]
            counters.update({f"normalize_{_owner}": 1})
            return _original(path)

        if owner == "indexing":
            indexing_module.normalize_path = traced
        else:
            exif_tool_module.normalize_path = traced

    def restore() -> None:
        indexing_module.normalize_path = originals["indexing"]
        exif_tool_module.normalize_path = originals["exif_tool"]

    return restore


def _write_profile_report(profile_paths: list[Path], report_path: Path) -> None:
    report = io.StringIO()
    for profile_path in profile_paths:
        report.write(f"===== {profile_path} =====\n\n")
        for sort_key in ("cumulative", "tottime"):
            report.write(f"-- top 30 by {sort_key} --\n")
            stats = pstats.Stats(str(profile_path), stream=report)
            stats.strip_dirs().sort_stats(sort_key).print_stats(30)
            report.write("\n")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report.getvalue(), encoding="utf-8")


def _measure(
    function: Callable[[], dict], profile_out: Path | None, instrument: bool
) -> dict:
    if not instrument:
        result = function()
        result["measurement_mode"] = "timing-only"
        return result

    tracemalloc.start()
    profiler = cProfile.Profile()
    profiler.enable()
    try:
        result = function()
    finally:
        profiler.disable()
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    result["measurement_mode"] = "cProfile+tracemalloc"
    result["peak_traced_memory_bytes"] = peak
    if profile_out is not None:
        profile_out.parent.mkdir(parents=True, exist_ok=True)
        profiler.dump_stats(str(profile_out))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--scenario",
        choices=("discovery", "sync", "refresh", "workspace", "all"),
        default="all",
    )
    parser.add_argument("--photos", type=int, default=1000)
    parser.add_argument("--depth", type=int, default=10)
    parser.add_argument("--profile-out", type=Path)
    parser.add_argument(
        "--no-profile",
        action="store_true",
        help="Measure timings without cProfile/tracemalloc overhead",
    )
    parser.add_argument(
        "--trace-normalization",
        action="store_true",
        help="Count normalize_path calls by owning module",
    )
    parser.add_argument(
        "--report-out",
        type=Path,
        help="Combined human-readable pstats report; defaults beside --profile-out",
    )
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args()
    if args.photos < 0 or args.depth < 1:
        parser.error("--photos must be non-negative and --depth must be positive")

    with tempfile.TemporaryDirectory(prefix="tagger-perf-") as temporary:
        root = Path(temporary) / "library"
        root.mkdir()
        paths = _make_fixture(root, args.photos, args.depth)
        scenarios = (
            ("discovery", "sync", "refresh", "workspace")
            if args.scenario == "all"
            else (args.scenario,)
        )
        results = []
        profile_paths: list[Path] = []
        for scenario in scenarios:
            counters: Counter[str] = Counter()
            if scenario == "refresh":
                _prepare_refresh(root, Counter(), paths)
            profile_out = None if args.no_profile else args.profile_out
            if profile_out is not None and len(scenarios) > 1:
                profile_out = profile_out.with_name(
                    f"{profile_out.stem}-{scenario}{profile_out.suffix or '.prof'}"
                )
            if profile_out is not None:
                profile_paths.append(profile_out)
            restore_trace = (
                _install_normalization_trace(counters)
                if args.trace_normalization
                else None
            )
            try:
                results.append(
                    _measure(
                        lambda scenario=scenario, counters=counters: _run_scenario(
                            scenario, root, paths, counters
                        ),
                        profile_out,
                        not args.no_profile,
                    )
                )
            finally:
                if restore_trace is not None:
                    restore_trace()

    output = {"photos": args.photos, "depth": args.depth, "results": results}
    rendered = json.dumps(output, indent=2)
    if args.json_out is None:
        print(rendered)
    else:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(rendered + os.linesep, encoding="utf-8")
        print(f"Wrote {args.json_out}")
    for profile_path in profile_paths:
        print(f"Wrote {profile_path}")
    if profile_paths:
        report_path = args.report_out
        if report_path is None:
            report_path = profile_paths[0].with_name(
                f"{profile_paths[0].stem.removesuffix('-discovery')}-report.txt"
            )
        _write_profile_report(profile_paths, report_path)
        print(f"Wrote combined pstats report {report_path}")


if __name__ == "__main__":
    main()
