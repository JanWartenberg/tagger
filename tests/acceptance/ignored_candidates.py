"""Persistent ignore scenarios using disposable real JPEGs and public Qt controls."""

import json
import os
from pathlib import Path
import sys

from PyQt6 import QtCore, QtTest, QtWidgets

from confirmed_copy import (
    application_window,
    cli,
    click,
    copy_control,
    emit,
    generate_photos,
    photo_hashes,
    wait,
)


def scan(app, window):
    wait(app, "scan enabled", window.duplicateStartScanButton.isEnabled)
    click(window.duplicateStartScanButton)
    wait(
        app,
        "scan finished",
        lambda: "Duplicate scan complete" in window.statusBar().currentMessage(),
    )


def ignore(app, window):
    wait(app, "ignore control visible", window.duplicateIgnoreButton.isVisible)
    group = next(
        button
        for button in window.duplicateCandidateQueue.findChildren(QtWidgets.QPushButton)
        if button.isChecked()
    )
    group.setFocus()
    QtTest.QTest.keyClick(group, QtCore.Qt.Key.Key_I)
    wait(
        app,
        "ignore saved",
        lambda: "ignored and remembered" in window.statusBar().currentMessage(),
    )
    assert not window.duplicateCandidateQueue.isVisible()


def inspect(app, window, expected=1):
    assert window.duplicateIgnoredCandidatesButton.isEnabled()
    # Offscreen Qt has no window manager to reactivate the parent after a dialog closes.
    window.activateWindow()
    wait(app, "Duplicate review window active", lambda: app.activeWindow() is window)
    window.duplicateIgnoredCandidatesButton.setFocus()
    QtTest.QTest.keyClick(
        window.duplicateIgnoredCandidatesButton,
        QtCore.Qt.Key.Key_I,
        QtCore.Qt.KeyboardModifier.ControlModifier,
    )
    wait(app, "ignored list", lambda: app.activeModalWidget() is not None)
    dialog = app.activeModalWidget()
    assert dialog.windowTitle() == "Ignored candidates"
    candidates = dialog.findChild(QtWidgets.QListWidget)
    wait(app, "remembered candidates", lambda: candidates.count() == expected)
    wait(
        app,
        "photo previews",
        lambda: sum(
            label.pixmap() is not None and not label.pixmap().isNull()
            for label in dialog.findChildren(QtWidgets.QLabel)
        )
        == 4,
    )
    text = " ".join(label.text() for label in dialog.findChildren(QtWidgets.QLabel))
    assert "Holiday" in text and "Tags when ignored:" in text
    return dialog


def main():
    app = QtWidgets.QApplication([])
    root = Path(os.environ["TAGGER_ACCEPTANCE_ROOT"])
    phase = os.environ["TAGGER_ACCEPTANCE_PHASE"]
    photos = root / "ignored-photos"
    evidence = root / "ignored-photo-hashes.json"
    if phase == "ignore":
        generate_photos(photos)
        before = photo_hashes(photos)
        evidence.write_text(json.dumps(before), encoding="utf-8")
    else:
        before = json.loads(evidence.read_text(encoding="utf-8"))
    with application_window(app) as window:
        window.handle_dropped_urls([QtCore.QUrl.fromLocalFile(str(photos))])
        wait(app, "four discovered photos", lambda: window.files.count() == 4)
        window.show_duplicate_review()
        scan(app, window)
        if phase == "ignore":
            wait(
                app,
                "source choice",
                lambda: copy_control(window, photos / "source.jpg", "source")
                is not None,
            )
            ignore(app, window)
            assert photo_hashes(photos) == before
            emit("ignore_remembered_without_photo_writes", hashes=before)
        else:
            assert not window.duplicateCandidateQueue.isVisible()
            dialog = inspect(app, window)
            QtTest.QTest.keyClick(dialog, QtCore.Qt.Key.Key_C)
            scan(app, window)
            assert not window.duplicateCandidateQueue.isVisible()
            assert photo_hashes(photos) == before
            emit("fresh_process_ignore_and_read_only_inspection", hashes=before)
            dialog = inspect(app, window)
            QtTest.QTest.keyClick(
                dialog.findChild(QtWidgets.QListWidget), QtCore.Qt.Key.Key_R
            )
            wait(
                app,
                "restored list",
                lambda: dialog.findChild(QtWidgets.QListWidget).count() == 0,
            )
            dialog.reject()
            assert window.duplicateCandidateQueue.isVisible()
            scan(app, window)
            assert window.duplicateCandidateQueue.isVisible()
            assert photo_hashes(photos) == before
            emit("explicit_restore_persists_without_photo_writes")
            ignore(app, window)
            dialog = inspect(app, window)
            failures = []

            def confirm_clear():
                try:
                    confirmation = app.activeModalWidget()
                    assert isinstance(confirmation, QtWidgets.QMessageBox)
                    click(confirmation.button(QtWidgets.QMessageBox.StandardButton.Yes))
                except BaseException as error:
                    failures.append(error)
                    app.activeModalWidget().reject()

            QtCore.QTimer.singleShot(0, confirm_clear)
            QtTest.QTest.keyClick(
                dialog.findChild(QtWidgets.QListWidget), QtCore.Qt.Key.Key_A
            )
            if failures:
                raise failures[0]
            wait(
                app,
                "cleared list",
                lambda: dialog.findChild(QtWidgets.QListWidget).count() == 0,
            )
            dialog.reject()
            scan(app, window)
            assert window.duplicateCandidateQueue.isVisible()
            assert photo_hashes(photos) == before
            emit("clear_all_ignores_without_photo_writes")
            ignore(app, window)
            for photo in photos.glob("*.jpg"):
                cli(
                    "-overwrite_original",
                    "-EXIF:DateTimeOriginal=",
                    "-EXIF:CreateDate=2024:02:03 12:00:00",
                    photo,
                )
            changed = photo_hashes(photos)
            assert changed != before
            scan(app, window)
            assert window.duplicateCandidateQueue.isVisible()
            assert photo_hashes(photos) == changed
            emit("changed_capture_evidence_returns_without_photo_writes")
            ignore(app, window)
            dialog = inspect(app, window, expected=2)
            candidates = dialog.findChild(QtWidgets.QListWidget)
            assert candidates.currentRow() == 0
            QtTest.QTest.keyClick(candidates, QtCore.Qt.Key.Key_J)
            assert candidates.currentRow() == 1
            assert "EXIF:DateTimeOriginal" in " ".join(
                label.text() for label in dialog.findChildren(QtWidgets.QLabel)
            )
            QtTest.QTest.keyClick(candidates, QtCore.Qt.Key.Key_K)
            assert candidates.currentRow() == 0
            assert "EXIF:CreateDate" in " ".join(
                label.text() for label in dialog.findChildren(QtWidgets.QLabel)
            )
            QtTest.QTest.keyClick(candidates, QtCore.Qt.Key.Key_C)
            wait(app, "ignored list closed", lambda: app.activeModalWidget() is None)
            assert photo_hashes(photos) == changed
            emit("ignored_list_keyboard_navigation_and_close")
    return 0


if __name__ == "__main__":
    sys.exit(main())
