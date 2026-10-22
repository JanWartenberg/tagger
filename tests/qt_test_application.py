"""One lazily created GUI application for the lifetime of the test process."""

from PyQt6 import QtWidgets


_application: QtWidgets.QApplication | None = None


def application() -> QtWidgets.QApplication:
    global _application
    if _application is None:
        # Closed windows and signal proxies can outlive their individual fixture.
        _application = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    return _application
