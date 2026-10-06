import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from types import SimpleNamespace

import pytest

from perf.profile_real import TAGS, read, reset_index
from tagger_app.exif_tool import KeywordState


@pytest.mark.skipif(shutil.which("exiftool") is None, reason="Real ExifTool required")
def test_pair_uses_both_orders_and_fresh_indexes(tmp_path):
    output = tmp_path / "paired.json"
    subprocess.run(
        [
            sys.executable,
            "perf/profile_real.py",
            "--photos",
            "201",
            "--repeats",
            "2",
            "--compare-batches",
            "--json-out",
            str(output),
        ],
        cwd=Path(__file__).resolve().parents[1],
        env={**os.environ, "QT_QPA_PLATFORM": "offscreen"},
        capture_output=True,
        text=True,
        check=True,
        timeout=90,
    )
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["warmup_seconds"] > 0
    assert len(report["results"]) == 12
    reads = [r for r in report["results"] if r["scenario"] == "read-batch"]
    assert [(r["repeat"], r["read_batch_size"]) for r in reads] == [
        (0, 200),
        (0, 1000),
        (1, 1000),
        (1, 200),
    ]
    for result in report["results"]:
        if result["scenario"] == "sync-unchanged":
            assert result["result"] == 0
            assert result["exiftool"].get("subprocess_calls", 0) == 0
        else:
            assert result["result"] == 201
            assert result["exiftool"]["subprocess_calls"] == (
                2 if result["read_batch_size"] == 200 else 1
            )
    assert len(report["paired_improvement"]["sync"]["per_pair_percent"]) == 2


def test_optimized_python_is_rejected_before_creating_output(tmp_path):
    output = tmp_path / "invalid.json"
    result = subprocess.run(
        [sys.executable, "-O", "perf/profile_real.py", "--json-out", str(output)],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode != 0
    assert "assertions are required" in result.stderr
    assert not output.exists()


@pytest.mark.parametrize("invalid", ["missing", "mirror", "date", "unreadable"])
def test_read_verification_rejects_incomplete_or_wrong_metadata(invalid):
    expected = [*TAGS, "Benchmark"]
    state = KeywordState(expected, expected, date_original="2024:02:03 12:00:00")
    states = {"photo.jpg": state}
    if invalid == "missing":
        states = {}
    elif invalid == "mirror":
        state.xmp = TAGS
    elif invalid == "date":
        state.date_original = None
    else:
        state.iptc_readable = False
    exif = SimpleNamespace(read_keywords_many=lambda _: states)
    with pytest.raises(AssertionError):
        read(exif, ["photo.jpg"], expected)


def test_index_reset_reports_deletion_failure(tmp_path, monkeypatch):
    (tmp_path / ".tagger").mkdir()

    def locked(*args, **kwargs):
        raise PermissionError("index locked")

    monkeypatch.setattr("perf.profile_real.shutil.rmtree", locked)
    with pytest.raises(PermissionError, match="index locked"):
        reset_index(tmp_path)
