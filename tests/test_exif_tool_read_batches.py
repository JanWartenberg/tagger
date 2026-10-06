import json
import math
import subprocess

import pytest

from tagger_app.exif_tool import ExifTool, ExifToolError


@pytest.mark.parametrize("count", [0, 1, 200, 201, 1000, 1001, 2001])
@pytest.mark.parametrize("override", [None, 200])
def test_large_reads_bound_process_count_and_preserve_records(
    tmp_path, monkeypatch, count, override
):
    batch_size = override or 1000
    if override is not None:
        monkeypatch.setattr("tagger_app.exif_tool._KEYWORD_READ_BATCH_SIZE", override)
    paths = [str(tmp_path / f"Möwe-{number}.jpg") for number in range(count)]
    batches = []

    def run(command, **kwargs):
        assert command[1:] == ["-charset", "filename=UTF8", "-@", "-"]
        arguments = kwargs["input"].decode("utf-8").splitlines()
        batch = [arg for arg in arguments if arg in requested]
        batches.append(batch)
        records = [
            {
                "SourceFile": path,
                "IPTC:Keywords": [f"Möwe-{path}"],
                "XMP-dc:Subject": ["Mirror"],
                "ExifIFD:DateTimeOriginal": "2024:02:03 12:00:00",
            }
            for path in batch
        ]
        return subprocess.CompletedProcess(
            command, 0, json.dumps(records).encode(), b""
        )

    requested = set(paths)
    monkeypatch.setattr("tagger_app.exif_tool.subprocess.run", run)
    states = ExifTool().read_keywords_many(paths)
    assert len(batches) == math.ceil(count / batch_size)
    assert all(len(batch) <= batch_size for batch in batches)
    assert [path for batch in batches for path in batch] == paths
    assert set(states) == requested
    for path, state in states.items():
        assert state.iptc == [f"Möwe-{path}"]
        assert state.xmp == ["Mirror"]
        assert state.date_original == "2024:02:03 12:00:00"


@pytest.mark.parametrize("failure", ["json", "process"])
@pytest.mark.parametrize("override", [None, 200])
def test_later_batch_failure_is_reported(tmp_path, monkeypatch, failure, override):
    if override is not None:
        monkeypatch.setattr("tagger_app.exif_tool._KEYWORD_READ_BATCH_SIZE", override)
    calls = 0

    def run(command, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            return subprocess.CompletedProcess(command, 0, b"[]", b"")
        if failure == "process":
            return subprocess.CompletedProcess(command, 1, b"", b"Read failed")
        return subprocess.CompletedProcess(command, 0, b"invalid JSON", b"")

    monkeypatch.setattr("tagger_app.exif_tool.subprocess.run", run)
    with pytest.raises(ExifToolError, match="Read failed|Failed to parse"):
        ExifTool().read_keywords_many(
            [str(tmp_path / f"photo-{i}.jpg") for i in range(1001)]
        )
