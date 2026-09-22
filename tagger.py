#!/usr/bin/env python3
"""Launcher for TAGGER: PyQt UI wrapper around the EXIF tool.

This is the entrypoint for TAGGER. It simply launches the PyQt UI
which in turn wraps the existing ExifTool-based logic.
"""

import sys

from PyQt6.QtWidgets import QApplication


def main():
    from exif_ui import MainWindow

    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
