"""Tests for platform-specific file-pane launch helpers."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from file_actions import FilePaneActions


class FilePaneActionsTests(unittest.TestCase):
    def test_windows_reveal_passes_the_file_as_explorer_select_target(self) -> None:
        path = r"C:\Photos\example.jpg"

        with (
            patch("file_actions.os.name", "nt"),
            patch("file_actions.subprocess.Popen") as popen,
        ):
            FilePaneActions().reveal(path)

        popen.assert_called_once_with(["explorer.exe", "/select,", path])


if __name__ == "__main__":
    unittest.main()
