"""Measure real metadata workflows using generated, disposable JPEG copies."""

from __future__ import annotations

import argparse
import cProfile
import hashlib
import json
import platform
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
import tracemalloc
from collections import Counter
from pathlib import Path
from unittest.mock import patch

from PyQt6 import QtGui

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tagger_app import exif_tool as exif_tool_module  # noqa: E402
from tagger_app.exif_tool import ExifTool  # noqa: E402
from tagger_app.indexing import IndexRefreshProgress, PhotoIndex  # noqa: E402
from tagger_app.photo_workspace import PhotoWorkspace  # noqa: E402
from tagger_app.services.photo_discovery import FileSystemPhotoDiscovery  # noqa: E402
from tagger_app.services.tag_mutation import TagMutationService  # noqa: E402

try:
    import resource
except ImportError:
    resource = None

REPO = Path(__file__).resolve().parents[1]
TAGS = ["Möwe", "Holiday"]
RUN_PROCESS = subprocess.run


def usage():
    if resource is None:
        return {}
    result = {}
    for name, who in (
        ("self", resource.RUSAGE_SELF),
        ("children", resource.RUSAGE_CHILDREN),
    ):
        value = resource.getrusage(who)
        result[f"{name}_cpu_seconds"] = value.ru_utime + value.ru_stime
        result[f"{name}_input_blocks"] = value.ru_inblock
        result[f"{name}_output_blocks"] = value.ru_oublock
    return result


class MeasuredExifTool(ExifTool):
    def __init__(self):
        super().__init__()
        self.counters = Counter()

    def _run(self, args):
        started = time.perf_counter()
        with patch(
            "tagger_app.exif_tool.subprocess.run",
            side_effect=lambda *a, **kw: RUN_PROCESS(*a, **kw, timeout=30),
        ):
            result = super()._run(args)
        self.counters["subprocess_calls"] += 1
        self.counters["subprocess_seconds"] += time.perf_counter() - started
        self.counters["stdout_bytes"] += len(result.encode("utf-8"))
        return result


class MeasuredIndex(PhotoIndex):
    def __init__(self, root):
        self.counters = Counter()
        super().__init__(root)

    def _connect(self):
        conn = super()._connect()
        conn.set_trace_callback(lambda _: self.counters.update(sqlite_statements=1))
        return conn


def fixture(root, count):
    # Same generated JPEG bytes for every run; never accept a personal-photo path.
    seed = root / "seed.jpg"
    image = QtGui.QImage(1024, 768, QtGui.QImage.Format.Format_RGB32)
    image.fill(QtGui.QColor("navy"))
    painter = QtGui.QPainter(image)
    for x in range(0, 1024, 16):
        for y in range(0, 768, 16):
            painter.fillRect(
                x, y, 16, 16, QtGui.QColor(x % 256, y % 256, (x + y) % 256)
            )
    painter.end()
    if not image.save(str(seed), "JPEG", 90):
        raise RuntimeError("Qt JPEG writer unavailable")
    exif = MeasuredExifTool()
    exif._run(
        [
            "-overwrite_original",
            "-charset",
            "IPTC=UTF8",
            "-IPTC:CodedCharacterSet=UTF8",
            "-EXIF:DateTimeOriginal=2024:02:03 12:00:00",
            *[f"-IPTC:Keywords={tag}" for tag in TAGS],
            *[f"-XMP-dc:Subject={tag}" for tag in TAGS],
            str(seed),
        ]
    )
    paths = []
    for number in range(count):
        directory = root / "Fotos ü" / f"album-{number % 10:02d}"
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"Möwe-{number:06d}.jpg"
        shutil.copyfile(seed, path)
        paths.append(str(path))
    fingerprint = hashlib.sha256(seed.read_bytes()).hexdigest()
    size = seed.stat().st_size
    seed.unlink()
    return paths, {
        "jpeg_bytes": size,
        "seed_sha256": fingerprint,
        "dimensions": [1024, 768],
    }


def measure(name, operation, exif, index, *, repeat, state, profile):
    exif.counters.clear()
    index.counters.clear()
    before = usage()
    if profile:
        tracemalloc.start()
    started = time.perf_counter()
    result = operation()
    elapsed = time.perf_counter() - started
    after = usage()
    memory = tracemalloc.get_traced_memory()[1] if profile else None
    if profile:
        tracemalloc.stop()
    return {
        "scenario": name,
        "repeat": repeat,
        "state": state,
        "elapsed_seconds": elapsed,
        "result": result,
        "exiftool": dict(exif.counters),
        "sqlite": dict(index.counters),
        "resource_delta": {key: after[key] - value for key, value in before.items()},
        "python_peak_bytes": memory,
    }


def read(exif, paths, expected_tags=TAGS):
    states = exif.read_keywords_many(paths)
    assert len(states) == len(paths)
    assert all(
        set(state.iptc) == set(expected_tags)
        and set(state.xmp) == set(expected_tags)
        and state.iptc_readable
        and state.xmp_readable
        and state.date_original == "2024:02:03 12:00:00"
        for state in states.values()
    )
    return len(states)


def refresh(index, exif, count):
    steps = 0
    while True:
        steps += 1
        result = index.refresh_step(exif)
        if not isinstance(result, IndexRefreshProgress):
            assert result.updated_count == count
            return {"updated": result.updated_count, "steps": steps}
        if steps > count + 100:
            raise RuntimeError("Refresh did not converge")


def save(exif, paths):
    result = TagMutationService(exif).add_tag(
        paths, "Benchmark", False, exif.read_keywords
    )
    assert result.changed_count == len(paths) and not result.failed_paths
    return result.changed_count


def workspace(paths):
    view = PhotoWorkspace()
    view.add_paths(paths)
    view.set_filename_filter("Möwe-0000")
    return len(view.snapshot().visible_paths)


def command(*args):
    return RUN_PROCESS(
        args, capture_output=True, text=True, check=True, timeout=30
    ).stdout.strip()


def reset_index(root):
    directory = root / ".tagger"
    if directory.exists():
        shutil.rmtree(directory)


def measure_pair(root, paths, exif, index, repeat, results):
    # Alternate order on one warmed fixture to reduce time/order confounding.
    sizes = (200, 1000) if repeat % 2 == 0 else (1000, 200)
    for position, size in enumerate(sizes):
        with patch.object(exif_tool_module, "_KEYWORD_READ_BATCH_SIZE", size):
            reset_index(root)
            for name, operation, expected in (
                ("read-batch", lambda: read(exif, paths), len(paths)),
                (
                    "sync",
                    lambda: index.sync_paths(exif, paths).updated_count,
                    len(paths),
                ),
                (
                    "sync-unchanged",
                    lambda: index.sync_paths(exif, paths).updated_count,
                    0,
                ),
            ):
                result = measure(
                    name,
                    operation,
                    exif,
                    index,
                    repeat=repeat,
                    state="same warmed files / fresh index per variant",
                    profile=False,
                )
                assert result["result"] == expected
                results.append(
                    {**result, "read_batch_size": size, "pair_position": position}
                )


def main():
    if not __debug__:
        raise SystemExit(
            "Run without Python optimization; benchmark assertions are required."
        )
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--photos", type=int, default=1000)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument(
        "--compare-batches",
        action="store_true",
        help="Alternate both read blocks on one warmed fixture; read/sync only",
    )
    parser.add_argument(
        "--read-batch-size",
        type=int,
        choices=(200, 1000),
        help="Compare the former and proposed read block on the same revision",
    )
    parser.add_argument("--json-out", type=Path, required=True)
    parser.add_argument(
        "--profile-out",
        type=Path,
        help="cProfile + tracemalloc diagnostic run; not a timing baseline",
    )
    args = parser.parse_args()
    if args.photos < 1 or args.repeats < 1:
        parser.error("--photos and --repeats must be positive")
    if args.compare_batches and (args.read_batch_size or args.profile_out):
        parser.error(
            "--compare-batches cannot be combined with --read-batch-size or --profile-out"
        )
    info = {
        "revision": command(
            "git", "-c", f"safe.directory={REPO}", "-C", str(REPO), "rev-parse", "HEAD"
        ),
        "working_tree": command(
            "git",
            "-c",
            f"safe.directory={REPO}",
            "--no-optional-locks",
            "-C",
            str(REPO),
            "status",
            "--short",
        ),
        "platform": platform.platform(),
        "python": sys.version,
        "exiftool": command("exiftool", "-ver"),
        "photos": args.photos,
        "read_batch_size": args.read_batch_size
        or exif_tool_module._KEYWORD_READ_BATCH_SIZE,
        "repeats": args.repeats,
        "compare_batches": args.compare_batches,
        "mode": "profile+tracemalloc" if args.profile_out else "timing-only",
        "cache_note": "Fresh DBs, OS caches already warm from fixture generation; no cold OS-cache claims.",
        "limits": "Generated JPEG copies, not camera originals. UI rendering not measured. Resource counters unavailable on Windows; block counts are OS I/O, not bytes.",
        "results": [],
    }
    profiler = cProfile.Profile() if args.profile_out else None
    with (
        patch.object(
            exif_tool_module, "_KEYWORD_READ_BATCH_SIZE", info["read_batch_size"]
        ),
        tempfile.TemporaryDirectory(prefix="tagger-real-perf-") as temporary,
    ):
        root = Path(temporary)
        paths, info["fixture"] = fixture(root, args.photos)
        exif = MeasuredExifTool()
        index = MeasuredIndex(root)
        if args.compare_batches:
            started = time.perf_counter()
            # A full, untimed 200-path read precedes both variants; first-read
            # outliers are recorded separately rather than hidden in medians.
            with patch.object(exif_tool_module, "_KEYWORD_READ_BATCH_SIZE", 200):
                read(exif, paths)
            info["warmup_seconds"] = time.perf_counter() - started
            info["cache_note"] = (
                "One generated fixture, full untimed metadata warmup, alternating variant order, fresh DB per variant. No cold-cache claim."
            )
        if profiler:
            profiler.enable()
        for repeat in range(args.repeats):
            if args.compare_batches:
                measure_pair(root, paths, exif, index, repeat, info["results"])
                continue
            operations = [
                ("startup", lambda: exif._run(["-ver"]).strip(), "warm process launch"),
                (
                    "discovery",
                    lambda: len(FileSystemPhotoDiscovery().discover(str(root))),
                    "warm filesystem",
                ),
                ("read-single", lambda: read(exif, paths[:1]), "warm filesystem"),
                ("read-batch", lambda: read(exif, paths), "warm filesystem"),
            ]
            # Each repeat starts with a fresh SQLite index, not a reused cache.
            reset_index(root)
            for name, operation, state in operations:
                info["results"].append(
                    measure(
                        name,
                        operation,
                        exif,
                        index,
                        repeat=repeat,
                        state=state,
                        profile=profiler is not None,
                    )
                )
            for name, operation, state in [
                (
                    "sync",
                    lambda: index.sync_paths(exif, paths).updated_count,
                    "fresh index / warm files",
                ),
                (
                    "sync-unchanged",
                    lambda: index.sync_paths(exif, paths).updated_count,
                    "warm index and files",
                ),
                (
                    "refresh",
                    lambda: refresh(index, exif, len(paths)),
                    "warm index / forced metadata reads",
                ),
                ("workspace", lambda: workspace(paths), "new workspace"),
            ]:
                info["results"].append(
                    measure(
                        name,
                        operation,
                        exif,
                        index,
                        repeat=repeat,
                        state=state,
                        profile=profiler is not None,
                    )
                )
            assert info["results"][-4]["result"] == len(paths)
            assert info["results"][-3]["result"] == 0
            for name, selected in [
                ("save-single", paths[:1]),
                ("save-selection", paths[:10]),
            ]:
                info["results"].append(
                    measure(
                        name,
                        lambda selected=selected: save(exif, selected),
                        exif,
                        index,
                        repeat=repeat,
                        state="warm / backups off",
                        profile=profiler is not None,
                    )
                )
                # Independent re-read verifies writes, then restore outside timings.
                read(exif, selected, [*TAGS, "Benchmark"])
                exif.write_keyword_fields(selected, TAGS, TAGS, False)
        if profiler:
            profiler.disable()
            args.profile_out.parent.mkdir(parents=True, exist_ok=True)
            profiler.dump_stats(str(args.profile_out))

    def result_key(result):
        name = result["scenario"]
        return f"{name}/{result['read_batch_size']}" if args.compare_batches else name

    info["medians_seconds"] = {
        name: statistics.median(
            r["elapsed_seconds"] for r in info["results"] if result_key(r) == name
        )
        for name in dict.fromkeys(result_key(r) for r in info["results"])
    }
    if args.compare_batches:
        gains = {}
        for name in ("read-batch", "sync", "sync-unchanged"):
            samples = []
            for repeat in range(args.repeats):
                timings = {
                    r["read_batch_size"]: r["elapsed_seconds"]
                    for r in info["results"]
                    if r["scenario"] == name and r["repeat"] == repeat
                }
                samples.append(100 * (1 - timings[1000] / timings[200]))
            gains[name] = {
                "per_pair_percent": samples,
                "median_percent": statistics.median(samples),
            }
        info["paired_improvement"] = gains
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(info, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(info["medians_seconds"], indent=2))
    print(f"Wrote {args.json_out}")


if __name__ == "__main__":
    main()
