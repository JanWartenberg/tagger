"""Focused operating-system and clipboard helpers for file-pane actions."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

from PyQt6 import QtCore, QtGui, QtWidgets

_WINDOWS_GIMP = Path(r"C:\Program Files\GIMP 3\bin\gimp-3.exe")


class FilePaneActions:
    """Perform file-pane actions through the host operating system."""

    def open_default(self, paths: tuple[str, ...]) -> None:
        for path in paths:
            opened = QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(path))
            if not opened:
                raise RuntimeError(f'Could not open "{path}"')

    def open_gimp(self, paths: tuple[str, ...]) -> None:
        executable = self._gimp_executable()
        if executable is None:
            raise RuntimeError("GIMP executable was not found")
        subprocess.Popen([executable, *paths])

    def copy_path(self, path: str) -> None:
        QtWidgets.QApplication.clipboard().setText(path)

    def reveal(self, path: str) -> None:
        if os.name == "nt":
            subprocess.Popen(["explorer.exe", f"/select,{path}"])
            return

        directory = str(Path(path).parent)
        launcher = (
            ["open", directory] if sys.platform == "darwin" else ["xdg-open", directory]
        )
        subprocess.Popen(launcher)

    def _gimp_executable(self) -> str | None:
        if _WINDOWS_GIMP.is_file():
            return str(_WINDOWS_GIMP)
        return shutil.which("gimp")
