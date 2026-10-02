"""Native sharing-lock partial failure and failed-only retry via public UI."""

import os
from pathlib import Path

from PyQt6 import QtCore, QtTest, QtWidgets

from confirmed_copy import (
    PHOTO_NAMES,
    application_window,
    assert_written,
    click,
    emit,
    generate_photos,
    metadata,
    photo_hashes,
    preview,
    select_copy_targets,
    tags,
    wait,
)
from windows_lock import read_only_sharing_lock


def status_row(window, status: str, successful: int, failed: int):
    expected = f"{successful} successful / {failed} failed / 0 pending"
    return next(
        (
            button
            for button in window.duplicateStatusRows.findChildren(QtWidgets.QPushButton)
            if button.text().startswith(f"{status} ·") and expected in button.text()
        ),
        None,
    )


def file_identity(path: Path) -> tuple[int, int, int]:
    stat = path.stat()
    return stat.st_ino, stat.st_mtime_ns, stat.st_ctime_ns


def locked_copy_scenario(app, root: Path, backup: bool) -> None:
    photos = root / "photos"
    generate_photos(photos)
    before = photo_hashes(photos)
    locked = photos / "empty-xmp.jpg"
    successful = photos / "mirror.jpg"
    with application_window(app) as window:
        select_copy_targets(app, window, photos, backup)
        dialog = preview(app, window)
        assert photo_hashes(photos) == before, "Preview wrote files"
        with read_only_sharing_lock(locked):
            # PyQt's stub omits staticmethod for this C++ namespace function.
            QtTest.QTest.keyClick(dialog, QtCore.Qt.Key.Key_Y)  # type: ignore[call-overload]
            wait(app, "preview closed", lambda: not dialog.isVisible())
            wait(
                app,
                "one success and one failure",
                lambda: status_row(window, "Failed", 1, 1),
            )
            wait(
                app,
                "writes drained",
                lambda: QtCore.QThreadPool.globalInstance().activeThreadCount() == 0,
            )
            partial = photo_hashes(photos)
            for name in ("source.jpg", "excluded.jpg", locked.name):
                assert partial[name] == before[name], f"Unwritten file changed: {name}"
            assert partial[successful.name] != before[successful.name]
            assert tags(metadata(successful), "IPTC:Keywords") == ["Holiday"]
            assert tags(metadata(successful), "XMP-dc:Subject") == ["Holiday"]
            assert tags(metadata(locked), "IPTC:Keywords") == []
            expected_names = set(PHOTO_NAMES)
            if backup:
                expected_names.add(successful.name + "_original")
                assert partial[successful.name + "_original"] == before[successful.name]
            assert set(partial) == expected_names, "Unexpected failed-write artifacts"
            emit(
                "sharing_lock_partial_failure",
                keep_backup=backup,
                before_sha256=before,
                after_sha256=partial,
                locked_target=str(locked),
                successful_target=str(successful),
            )
            click(status_row(window, "Failed", 1, 1))
            labels = [
                label.text()
                for label in window.findChildren(QtWidgets.QLabel)
                if label.isVisible()
            ]
            assert f"{successful}: successful" in labels, labels
            assert f"{locked}: failed" in labels, labels
            retry = next(
                button
                for button in window.findChildren(QtWidgets.QPushButton)
                if button.isVisible() and button.text() == "Retry failed targets"
            )
            assert retry.isEnabled()
        # Lock has been released. Retry is explicit, never automatic.
        assert photo_hashes(photos) == partial
        unchanged_identities = {
            name: file_identity(photos / name)
            for name in partial
            if name != locked.name
        }
        click(retry)
        wait(
            app,
            "all targets completed after retry",
            lambda: status_row(window, "Completed", 2, 0),
        )
        wait(
            app,
            "retry writes drained",
            lambda: QtCore.QThreadPool.globalInstance().activeThreadCount() == 0,
        )
        after = photo_hashes(photos)
        for name, identity in unchanged_identities.items():
            assert after[name] == partial[name], (
                f"Retry changed successful/unselected file: {name}"
            )
            assert file_identity(photos / name) == identity, (
                f"Retry rewrote file: {name}"
            )
        assert after[locked.name] != before[locked.name]
        expected_names = set(PHOTO_NAMES)
        if backup:
            expected_names.update(
                name + "_original" for name in (successful.name, locked.name)
            )
            for name in (successful.name, locked.name):
                assert after[name + "_original"] == before[name]
        assert set(after) == expected_names
        records = assert_written(photos)
        emit(
            "sharing_lock_failed_only_retry",
            keep_backup=backup,
            metadata=records,
            before_retry_sha256=partial,
            after_sha256=after,
            unchanged_file_identities=unchanged_identities,
        )
    assert photo_hashes(photos) == after


def run() -> None:
    if os.name != "nt":
        raise RuntimeError("Do not claim sharing-lock acceptance outside Windows")
    if not __debug__:
        raise RuntimeError("Assertions must be enabled")
    app = QtWidgets.QApplication([])
    app.setQuitOnLastWindowClosed(False)
    root = Path(os.environ["TAGGER_ACCEPTANCE_ROOT"])
    QtCore.QSettings.setDefaultFormat(QtCore.QSettings.Format.IniFormat)
    QtCore.QSettings.setPath(
        QtCore.QSettings.Format.IniFormat,
        QtCore.QSettings.Scope.UserScope,
        str(root / "settings"),
    )
    locked_copy_scenario(app, root, os.environ["TAGGER_ACCEPTANCE_BACKUP"] == "on")


if __name__ == "__main__":
    run()
