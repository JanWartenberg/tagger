import base64
import json

import pytest

from tagger_app.exif_tool import ExifTool, ExifToolError, _valid_iptc_block


@pytest.mark.parametrize(
    ("block", "valid"),
    [
        (b"\x1c\x02\x19\x00\x03cat", True),
        (b"\x1c\x02\x19\x80\x02\x00\x03cat", True),
        (b"\x1c\x02\x19\x00\x03cat\x00\x00", True),
        (b"\x1c\x02\x19\xff\xffcat", False),
        (b"\x1c\x02\x19\x00\x04cat", False),
        (b"\x1c\x02\x19\x80\x02\x00", False),
        (b"\x1c\x02\x19\x80\x00", False),
        (b"\x1c\x02\x19", False),
        (b"\x1c\x02\x19\x00\x03cat\x00\x01", False),
    ],
)
def test_iptc_block_framing(block: bytes, valid: bool) -> None:
    encoded = "base64:" + base64.b64encode(block).decode("ascii")
    assert _valid_iptc_block(encoded) is valid


@pytest.mark.parametrize("value", [None, "", "base64:***", "plain text"])
def test_iptc_block_rejects_unusable_transport(value: object) -> None:
    assert not _valid_iptc_block(value)


def test_iptc_block_rejects_oversized_data() -> None:
    encoded = "base64:" + base64.b64encode(b"\0" * (1024 * 1024 + 1)).decode()
    assert not _valid_iptc_block(encoded)


def test_iptc_block_accepts_large_extended_record() -> None:
    block = b"\x1c\x02\x78\x80\x02\x80\x00" + b"x" * 32768
    assert _valid_iptc_block("base64:" + base64.b64encode(block).decode())


def test_single_photo_read_does_not_treat_a_missing_record_as_empty(monkeypatch):
    exif = ExifTool()
    monkeypatch.setattr(exif, "_run", lambda _args: "[]")
    with pytest.raises(ExifToolError, match="did not return metadata"):
        exif.read_keywords("missing.jpg")


def test_single_photo_read_refuses_tags_without_the_requested_raw_block(monkeypatch):
    exif = ExifTool()

    def output(args):
        return json.dumps([{"SourceFile": args[-1], "IPTC:Keywords": "existing"}])

    monkeypatch.setattr(exif, "_run", output)
    state = exif.read_keywords("photo.jpg")
    assert state.iptc == ["existing"]
    assert not state.iptc_readable
