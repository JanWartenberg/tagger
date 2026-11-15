"""Native delayed mouse scrolling with production Qt, indexing and JPEGs."""

import os
from pathlib import Path

from PyQt6 import QtCore, QtGui, QtTest, QtWidgets

from confirmed_copy import application_window, cli, digest, emit, wait


def main():
    app = QtWidgets.QApplication([])
    folder = Path(os.environ["TAGGER_ACCEPTANCE_ROOT"]) / "photos"
    folder.mkdir()
    (folder / "a").mkdir()
    paths = [
        (folder if index < 100 else folder / "a")
        / f"z-{'long-photo-name-' * 6}{index:04d}.jpg"
        for index in range(200)
    ]
    image = QtGui.QImage(64, 48, QtGui.QImage.Format.Format_RGB32)
    image.fill(QtGui.QColor("blue"))
    for path in paths:
        assert image.save(str(path), "JPEG")
    cli("-overwrite_original", "-IPTC:Keywords=Tagged", *paths[:80])
    before = {str(path.relative_to(folder)): digest(path) for path in paths}
    native_delay = QtWidgets.QApplication.doubleClickInterval() + 100

    with application_window(app) as window:
        window.handle_dropped_urls([QtCore.QUrl.fromLocalFile(str(folder))])
        wait(
            app,
            "discovered photos",
            lambda: window.files.count() == 200 and window.files.isEnabled(),
        )
        window.onlyUntagged.setChecked(True)
        wait(
            app,
            "stable No tags results",
            lambda: window.statusBar().currentMessage() == "IPTC-empty results ready",
        )
        view = window.files
        assert all(view.item(row).isHidden() for row in range(80))
        assert not any(view.item(row).isHidden() for row in range(80, 200))
        assert [view.item(row).text() for row in range(200)] == list(map(str, paths))
        window.activateWindow()
        window.raise_()
        view.setCurrentRow(100)
        QtTest.QTest.qWait(native_delay + 100)
        view.scrollToItem(
            view.item(100), QtWidgets.QAbstractItemView.ScrollHint.PositionAtTop
        )
        app.processEvents()
        bar = view.verticalScrollBar()
        anchor = bar.value()
        target = view.item(101)
        rect = view.visualItemRect(target)
        assert rect.width() > view.viewport().width(), "Need overflowing paths"
        assert rect.top() >= 0 and rect.bottom() < view.viewport().height()
        QtTest.QTest.mouseClick(
            view.viewport(),
            QtCore.Qt.MouseButton.LeftButton,
            pos=QtCore.QPoint(20, rect.center().y()),
        )
        QtTest.QTest.qWait(native_delay + 100)
        assert window.active_file_path() == str(paths[101])
        assert bar.value() == anchor, (anchor, bar.value())
        assert view.visualItemRect(target).intersects(view.viewport().rect())
        emit(
            "native_filtered_adjacent_click",
            scroll_before=anchor,
            scroll_after=bar.value(),
        )

        bar.setValue(anchor + 7)
        anchor = bar.value()
        assert view.visualItemRect(view.item(100)).top() == -7
        rect = view.visualItemRect(view.item(102))
        QtTest.QTest.mouseClick(
            view.viewport(),
            QtCore.Qt.MouseButton.LeftButton,
            pos=QtCore.QPoint(20, rect.center().y()),
        )
        QtTest.QTest.qWait(native_delay + 100)
        assert window.active_file_path() == str(paths[102])
        assert bar.value() == anchor, (anchor, bar.value())
        view.setFocus()
        QtTest.QTest.keyClick(
            view,
            QtCore.Qt.Key.Key_G,
            QtCore.Qt.KeyboardModifier.ShiftModifier,
        )
        wait(
            app,
            "last photo selected",
            lambda: window.active_file_path() == str(paths[-1]),
        )
        assert view.visualItemRect(view.item(199)).intersects(view.viewport().rect())
        # A subsequent explicit user scroll must remain effective.
        bar.triggerAction(QtWidgets.QAbstractSlider.SliderAction.SliderToMinimum)
        QtTest.QTest.qWait(native_delay + 100)
        assert bar.value() == 0
        assert {
            str(p.relative_to(folder)): digest(p)
            for directory in (folder, folder / "a")
            for p in directory.iterdir()
            if p.is_file()
        } == before
        emit("partial_anchor_and_explicit_scroll", jpeg_hashes_unchanged=True)


if __name__ == "__main__":
    main()
