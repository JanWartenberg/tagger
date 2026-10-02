"""Real-file UI scenarios, launched only by run.py in an isolated child."""

from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from PyQt6 import QtCore, QtGui, QtTest, QtWidgets

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tagger_app.ui.main_window import MainWindow  # noqa: E402


PHOTO_NAMES = ("source.jpg", "mirror.jpg", "empty-xmp.jpg", "excluded.jpg")
TARGET_NAMES = ("mirror.jpg", "empty-xmp.jpg")


def cli(*args):
    result = subprocess.run(
        ["exiftool", *map(str, args)], capture_output=True, text=True, timeout=15
    )
    if result.returncode:
        raise RuntimeError(f"ExifTool {args}: {result.stderr}")
    return result.stdout


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def photo_hashes(photos):
    # Include unexpected files/backups too, but not the app's mutable index directory.
    return {p.name: digest(p) for p in sorted(photos.iterdir()) if p.is_file()}


def metadata(path):
    return json.loads(cli("-j", "-G1", "-IPTC:Keywords", "-XMP-dc:Subject", path))[0]


def tags(record, field):
    value = record.get(field, [])
    return [value] if isinstance(value, str) else value


def emit(case, **observations):
    print(json.dumps({"case": case, "status": "passed", **observations}), flush=True)


def wait(app, description, predicate, timeout=20):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        app.processEvents()
        if predicate():
            return
        QtTest.QTest.qWait(10)
    raise AssertionError(f"Timed out waiting for {description}")


def click(control):
    assert control.isEnabled(), f"Disabled control: {control.text()}"
    QtTest.QTest.mouseClick(
        control,
        QtCore.Qt.MouseButton.LeftButton,
        pos=QtCore.QPoint(8, control.height() // 2),
    )


@contextmanager
def application_window(app):
    window = MainWindow()
    window.show()
    try:
        yield window
    except BaseException:
        print(
            "UI labels: "
            + repr([x.text() for x in window.findChildren(QtWidgets.QLabel)]),
            file=sys.stderr,
        )
        print("Status: " + window.statusBar().currentMessage(), file=sys.stderr)
        raise
    finally:
        window.close()
        # Keep Qt alive until production workers finish; parent enforces a hard deadline.
        wait(
            app,
            "worker cleanup",
            lambda: QtCore.QThreadPool.globalInstance().activeThreadCount() == 0,
        )
        app.processEvents()
        window.deleteLater()
        QtCore.QCoreApplication.sendPostedEvents(
            None, QtCore.QEvent.Type.DeferredDelete
        )


def generate_photos(photos):
    photos.mkdir()
    for name, color in zip(
        PHOTO_NAMES, ("red", "blue", "green", "yellow"), strict=True
    ):
        path = photos / name
        image = QtGui.QImage(64, 48, QtGui.QImage.Format.Format_RGB32)
        image.fill(QtGui.QColor(color))
        assert image.save(str(path), "JPEG"), "Qt JPEG writer unavailable"
        cli("-overwrite_original", "-EXIF:DateTimeOriginal=2024:02:03 12:00:00", path)
    # Deliberately disagreeing source mirror must not become canonical copied tags.
    cli(
        "-overwrite_original",
        "-IPTC:Keywords=Holiday",
        "-XMP-dc:Subject=Source mirror only",
        photos / "source.jpg",
    )
    for name in ("mirror.jpg", "excluded.jpg"):
        cli("-overwrite_original", "-XMP-dc:Subject=Old mirror", photos / name)
    records = {name: metadata(photos / name) for name in PHOTO_NAMES}
    assert tags(records["source.jpg"], "IPTC:Keywords") == ["Holiday"]
    assert tags(records["source.jpg"], "XMP-dc:Subject") == ["Source mirror only"]
    for name in PHOTO_NAMES[1:]:
        assert tags(records[name], "IPTC:Keywords") == []
        assert tags(records[name], "XMP-dc:Subject") == (
            [] if name == "empty-xmp.jpg" else ["Old mirror"]
        )
    assert set(photo_hashes(photos)) == set(PHOTO_NAMES)


def copy_control(window, path, role):
    kind = QtWidgets.QRadioButton if role == "source" else QtWidgets.QCheckBox
    return next(
        (
            control
            for control in window.findChildren(kind)
            if control.accessibleName() == f"Use {path} as {role}"
            and control.isVisible()
        ),
        None,
    )


def preview(app, window):
    wait(app, "copy enabled", window.duplicateApplyTagsButton.isEnabled)
    click(window.duplicateApplyTagsButton)

    def visible_dialog():
        return next(
            (
                d
                for d in window.findChildren(QtWidgets.QDialog)
                if d.objectName() == "duplicateCopyPreview" and d.isVisible()
            ),
            None,
        )

    wait(app, "copy preview", visible_dialog)
    return visible_dialog()


def assert_written(photos):
    records = {name: metadata(photos / name) for name in TARGET_NAMES}
    for name, record in records.items():
        assert tags(record, "IPTC:Keywords") == ["Holiday"], record
        expected_xmp = ["Holiday"] if name == "mirror.jpg" else []
        assert tags(record, "XMP-dc:Subject") == expected_xmp, record
        assert not QtGui.QImage(str(photos / name)).isNull(), f"Unreadable JPEG: {name}"
    return records


def select_copy_targets(app, window, photos, keep_backup):
    window.handle_dropped_urls([QtCore.QUrl.fromLocalFile(str(photos))])
    wait(app, "four discovered photos", lambda: window.files.count() == 4)
    assert not window.keepBackup.isChecked(), "Fresh backup setting must be off"
    if keep_backup:
        click(window.keepBackup)
    assert window.keepBackup.isChecked() == keep_backup
    window.show_duplicate_review()
    wait(app, "scan enabled", window.duplicateStartScanButton.isEnabled)
    click(window.duplicateStartScanButton)
    wait(
        app,
        "source choice",
        lambda: copy_control(window, photos / "source.jpg", "source"),
    )
    click(copy_control(window, photos / "source.jpg", "source"))
    for name in PHOTO_NAMES[1:]:
        assert copy_control(window, photos / name, "target").isChecked()
    click(copy_control(window, photos / "excluded.jpg", "target"))
    assert not copy_control(window, photos / "excluded.jpg", "target").isChecked()


def copy_scenario(app, root, keep_backup):
    photos = root / "photos"
    generate_photos(photos)
    before = photo_hashes(photos)
    with application_window(app) as window:
        select_copy_targets(app, window, photos, keep_backup)

        for decision in (QtCore.Qt.Key.Key_N, QtCore.Qt.Key.Key_Y):
            dialog = preview(app, window)
            text = " ".join(x.text() for x in dialog.findChildren(QtWidgets.QLabel))
            for name in ("source.jpg", *TARGET_NAMES):
                assert str(photos / name) in text, text
            assert str(photos / "excluded.jpg") not in text, text
            assert "Holiday" in text and "Source mirror only" not in text, text
            assert f"Backup: {'on' if keep_backup else 'off'}" in text, text
            assert photo_hashes(photos) == before, "Preview wrote files"
            QtTest.QTest.keyClick(dialog, decision)
            wait(app, "preview closed", lambda: not dialog.isVisible())
            if decision == QtCore.Qt.Key.Key_N:
                wait(
                    app,
                    "cancelled work drained",
                    lambda: QtCore.QThreadPool.globalInstance().activeThreadCount()
                    == 0,
                )
                assert photo_hashes(photos) == before, (
                    "Cancellation wrote files/backups"
                )
                emit(
                    "cancel_copy",
                    before_sha256=before,
                    after_sha256=photo_hashes(photos),
                )

        wait(
            app,
            "completed copy outcome",
            lambda: any(
                "Completed" in b.text()
                for b in window.duplicateStatusRows.findChildren(QtWidgets.QPushButton)
            ),
        )
        records = assert_written(photos)
        after = photo_hashes(photos)
        for name in ("source.jpg", "excluded.jpg"):
            assert after[name] == before[name], f"Unselected file changed: {name}"
        for name in TARGET_NAMES:
            assert after[name] != before[name], f"Selected target unchanged: {name}"
        expected_names = set(PHOTO_NAMES)
        if keep_backup:
            expected_names.update(name + "_original" for name in TARGET_NAMES)
            for name in TARGET_NAMES:
                assert after[name + "_original"] == before[name], (
                    "Backup differs from original JPEG"
                )
        assert set(after) == expected_names, (
            f"Unexpected or missing backups/files: {after.keys()}"
        )
        emit(
            "confirmed_subset",
            metadata=records,
            before_sha256=before,
            after_sha256=after,
        )
        emit("backup_policy", keep_backup=keep_backup, files=sorted(after))
    # Snapshot after the writing application has shut down, for a separate reader process.
    assert photo_hashes(photos) == after
    (root / "written.json").write_text(
        json.dumps({"writer_pid": os.getpid(), "hashes": after}), encoding="utf-8"
    )


def reopen_scenario(app, root):
    photos = root / "photos"
    evidence = json.loads((root / "written.json").read_text(encoding="utf-8"))
    assert photo_hashes(photos) == evidence["hashes"]
    # A new process and a new window per target prevent any in-memory tag reuse.
    for name in TARGET_NAMES:
        with application_window(app) as window:
            assert window.keywordsList.count() == 0
            target = photos / name
            window.handle_dropped_urls([QtCore.QUrl.fromLocalFile(str(target))])
            wait(
                app,
                f"fresh read of {name}",
                lambda: (
                    window.files.count() == 1
                    and window.selectedLabel.text() == str(target)
                    and [
                        window.keywordsList.item(i).text()
                        for i in range(window.keywordsList.count())
                    ]
                    == ["Holiday"]
                ),
            )
    records = assert_written(photos)
    assert photo_hashes(photos) == evidence["hashes"], "Reopening changed JPEGs/backups"
    emit(
        "fresh_application_persistence",
        writer_pid=evidence["writer_pid"],
        reader_pid=os.getpid(),
        metadata=records,
        hashes=photo_hashes(photos),
    )


def run():
    if not __debug__:
        raise RuntimeError("Assertions must be enabled")
    root = Path(os.environ["TAGGER_ACCEPTANCE_ROOT"])
    phase = os.environ.get("TAGGER_ACCEPTANCE_PHASE", "copy")
    keep_backup = os.environ.get("TAGGER_ACCEPTANCE_BACKUP", "off") == "on"
    app = QtWidgets.QApplication([])
    app.setQuitOnLastWindowClosed(False)
    QtCore.QSettings.setDefaultFormat(QtCore.QSettings.Format.IniFormat)
    QtCore.QSettings.setPath(
        QtCore.QSettings.Format.IniFormat,
        QtCore.QSettings.Scope.UserScope,
        str(root / "settings"),
    )
    if phase == "copy":
        copy_scenario(app, root, keep_backup)
    elif phase == "reopen":
        reopen_scenario(app, root)
    else:
        raise ValueError(f"Unknown phase: {phase}")


if __name__ == "__main__":
    print(
        json.dumps({"qt": QtCore.qVersion(), "pyqt": QtCore.PYQT_VERSION_STR}),
        flush=True,
    )
    run()
