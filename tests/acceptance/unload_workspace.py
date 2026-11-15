"""Unload through public Qt controls using disposable photos and real ExifTool."""

import os
from pathlib import Path

from PyQt6 import QtCore, QtWidgets, QtTest

from confirmed_copy import (
    application_window,
    click,
    generate_photos,
    emit,
    photo_hashes,
    wait,
)


def command(window, text):
    window.cmdLine.show()
    window.cmdLine.setText(f":{text}")
    QtTest.QTest.keyClick(window.cmdLine, QtCore.Qt.Key.Key_Return)


def main():
    app = QtWidgets.QApplication([])
    root = Path(os.environ["TAGGER_ACCEPTANCE_ROOT"])
    photos = root / "photos"
    generate_photos(photos)
    before = photo_hashes(photos)
    with application_window(app) as window:

        def load():
            window.handle_dropped_urls([QtCore.QUrl.fromLocalFile(str(photos))])
            wait(app, "photos loaded", lambda: window.files.count() == 4)

        load()
        window.show_duplicate_review()
        wait(app, "duplicate scope ready", window.duplicateStartScanButton.isEnabled)
        click(window.duplicateStartScanButton)
        wait(app, "candidate cards", window.duplicateResultsScroll.isVisible)
        click(window.duplicateUnloadButton)
        assert window.files.count() == 0
        assert not window.duplicateResultsScroll.isVisible()
        assert not window.duplicateStartScanButton.isEnabled()
        assert window.duplicateScopeSizeLabel.text() == "Waiting for a photo folder"
        assert (photos / ".tagger" / "index.sqlite").is_file()
        assert photo_hashes(photos) == before
        emit("eject_clears_duplicate_results_without_photo_writes")

        window.show_tagging_workspace()
        load()
        window.filenameFilterEdit.setText("source")
        window.addEdit.setText("draft")
        backup = window.keepBackup.isChecked()
        command(window, "unload")
        QtTest.QTest.qWait(350)
        assert window.files.count() == 0
        assert window.keywordsList.count() == 0
        assert window.dateLabel.text() == ""
        assert window.filenameFilterEdit.text() == ""
        assert window.addEdit.text() == ""
        assert window.keepBackup.isChecked() == backup
        assert window.statusBar().currentMessage() == "Workspace unloaded"
        load()
        window.dbSearchEdit.setText("Holiday")
        QtTest.QTest.keyClick(window.dbSearchEdit, QtCore.Qt.Key.Key_Return)
        wait(app, "preserved index search", lambda: window.files.count() == 1)
        assert window.files.item(0).text() == str(photos / "source.jpg")
        assert photo_hashes(photos) == before
        emit("unload_command_resets_filters_and_preserves_index_and_photos")


if __name__ == "__main__":
    main()
