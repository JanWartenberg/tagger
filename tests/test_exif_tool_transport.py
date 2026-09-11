"""Regression coverage for Unicode arguments at the subprocess boundary."""

import json
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

from exif_tool import ExifTool, ExifToolError


class ExifToolTransportTests(unittest.TestCase):
    def test_unicode_photo_is_returned_under_its_requested_path(self):
        photo = str(Path("Korallenmöwe_01.JPG").resolve())

        def execute(command, **kwargs):
            self.assertEqual(command[1:], ["-charset", "filename=UTF8", "-@", "-"])
            self.assertIn(photo, kwargs["input"].decode("utf-8").splitlines())
            self.assertNotIn("text", kwargs)
            return subprocess.CompletedProcess(
                command,
                0,
                json.dumps(
                    [{"SourceFile": photo, "IPTC:Keywords": ["Korallenmöwe"]}],
                    ensure_ascii=False,
                ).encode("utf-8"),
                b"",
            )

        with patch("exif_tool.subprocess.run", side_effect=execute):
            state = ExifTool().read_keywords_many([photo])[photo]
        self.assertTrue(state.iptc_readable)
        self.assertEqual(state.iptc, ["Korallenmöwe"])

    def test_writes_unicode_keywords_and_paths_as_utf8(self):
        with patch(
            "exif_tool.subprocess.run",
            return_value=subprocess.CompletedProcess([], 0, b"", b""),
        ) as run:
            ExifTool().write_keyword_fields(
                ["Korallenmöwe.JPG"], ["Möwe"], ["Möwe"], keep_backup=True
            )
        arguments = run.call_args.kwargs["input"].decode("utf-8").splitlines()
        self.assertIn("-IPTC:Keywords=Möwe", arguments)
        self.assertIn("Korallenmöwe.JPG", arguments)

    def test_rejects_line_breaks_before_starting_process(self):
        for argument in ("photo\n-overwrite_original", "photo\r.jpg"):
            with self.subTest(argument=argument):
                with patch("exif_tool.subprocess.run") as run:
                    with self.assertRaises(ExifToolError):
                        ExifTool()._run([argument])
                    run.assert_not_called()

    def test_reports_decoded_process_error(self):
        with patch(
            "exif_tool.subprocess.run",
            return_value=subprocess.CompletedProcess(
                [], 1, b"", "Cannot read Möwe.JPG".encode("utf-8")
            ),
        ):
            with self.assertRaisesRegex(ExifToolError, "Cannot read Möwe.JPG"):
                ExifTool()._run(["Möwe.JPG"])


if __name__ == "__main__":
    unittest.main()
