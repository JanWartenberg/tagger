"""Scoped refresh with production Qt, discovery, SQLite, and ExifTool."""

import os
from pathlib import Path
import subprocess
import sys

from PyQt6 import QtCore, QtGui, QtTest, QtWidgets

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tagger_app.exif_tool import ExifTool  # noqa: E402
from tagger_app.indexing import PhotoIndex  # noqa: E402
from tagger_app.storage import save_config  # noqa: E402
from confirmed_copy import application_window, cli, digest, emit, wait  # noqa: E402


def make_photo(path, date):
    path.parent.mkdir(parents=True, exist_ok=True)
    image = QtGui.QImage(64, 48, QtGui.QImage.Format.Format_RGB32)
    image.fill(QtGui.QColor("blue"))
    assert image.save(str(path), "JPEG")
    cli("-overwrite_original", f"-EXIF:DateTimeOriginal={date}", path)


def choose_folder(app, window, folder):
    # Exercise the public picker without desktop-wide/native input automation.
    timer = QtCore.QTimer()

    def accept_picker():
        dialog = app.activeModalWidget()
        if isinstance(dialog, QtWidgets.QFileDialog):
            dialog.setDirectory(str(folder))
            timer.stop()
            QtTest.QTest.keyClick(dialog, QtCore.Qt.Key.Key_Return)

    timer.timeout.connect(accept_picker)
    timer.start(20)
    try:
        window.add_folder_dialog()
    finally:
        timer.stop()


def command(window, text):
    window.cmdLine.show()
    window.cmdLine.setText(text)
    QtTest.QTest.keyClick(window.cmdLine, QtCore.Qt.Key.Key_Return)


def main():
    QtWidgets.QApplication.setAttribute(
        QtCore.Qt.ApplicationAttribute.AA_DontUseNativeDialogs
    )
    app = QtWidgets.QApplication([])
    root = Path(os.environ["TAGGER_ACCEPTANCE_ROOT"]) / "folder-refresh-library"
    folder, sibling = root / "birds", root / "birds-other"
    keep, changed, gone = [
        folder / name for name in ("keep.jpg", "changed.jpg", "gone.jpg")
    ]
    outside = sibling / "outside.jpg"
    for path in (keep, changed, gone, outside):
        make_photo(path, "2026:09:18 08:09:00")
    save_config({"default_index_root": str(root)})
    index = PhotoIndex(root)
    index.sync_paths(ExifTool(), [str(p) for p in (keep, changed, gone, outside)])
    freshness = index.last_index_refresh()
    with application_window(app) as window:
        choose_folder(app, window, folder)
        wait(
            app,
            "initial folder",
            lambda: window.files.count() == 3 and window.files.isEnabled(),
        )
        item = next(
            window.files.item(i)
            for i in range(window.files.count())
            if window.files.item(i).text() == str(keep)
        )
        window.activateWindow()
        window.raise_()
        app.processEvents()
        QtTest.QTest.mouseClick(
            window.files.viewport(),
            QtCore.Qt.MouseButton.LeftButton,
            pos=window.files.visualItemRect(item).center(),
        )
        gone.unlink()
        cli(
            "-overwrite_original", "-EXIF:DateTimeOriginal=2026:10:18 08:09:00", changed
        )
        added = folder / "nested" / "DSC06827.JPG"
        make_photo(added, "2026:10:18 08:09:00")
        unseen = sibling / "unseen.jpg"
        make_photo(unseen, "2026:10:18 08:09:00")
        for name, destination in (("sibling-link", sibling), ("ancestor-link", folder)):
            link = folder / name
            if os.name == "nt":
                subprocess.run(
                    ["cmd", "/c", "mklink", "/J", str(link), str(destination)],
                    check=True,
                    capture_output=True,
                    timeout=15,
                )
            else:
                link.symlink_to(destination, target_is_directory=True)
        # This marker must not shadow the active library database.
        (folder / ".tagger").mkdir()
        before = {str(p): digest(p) for p in (keep, changed, added, outside, unseen)}
        window.files.setFocus()
        QtTest.QTest.keyClick(window.files, QtCore.Qt.Key.Key_F5)
        wait(
            app,
            "folder refresh",
            lambda: window.indexRepairStatusLabel.text().startswith(
                "Folder refreshed:"
            ),
        )
        assert set(window.all_file_paths()) == {str(keep), str(changed), str(added)}
        assert window.active_file_path() == str(keep)
        assert set(index.search_photos("date:2026-10")) == {str(changed), str(added)}
        assert index.has_photos([str(gone), str(unseen)]) == set()
        assert index.has_photos([str(outside)]) == {str(outside)}
        assert not (folder / ".tagger" / "index.sqlite").exists()
        assert index.last_index_refresh() == freshness
        emit(
            "folder_refresh_scoped_reconciliation",
            target=str(folder),
            unchanged_sibling=str(outside),
            redirected_directories="native junctions"
            if os.name == "nt"
            else "symbolic links",
        )
        window.dbDateSearchEdit.setText("2026-10")
        window.apply_db_search()
        wait(
            app,
            "initial date search",
            lambda: window.statusBar().currentMessage().startswith("DB search:"),
        )
        second = folder / "DSC06828.JPG"
        make_photo(second, "2026:10:18 08:09:00")
        before[str(second)] = digest(second)
        command(window, ":refreshfolder")
        wait(
            app, "refreshed date search", lambda: str(second) in window.all_file_paths()
        )
        assert set(window.all_file_paths()) == {str(changed), str(added), str(second)}
        assert index.has_photos([str(unseen)]) == set()
        assert {path: digest(Path(path)) for path in before} == before
        emit(
            "folder_refresh_reapplies_date_search",
            matches=len(window.all_file_paths()),
            photos_unchanged=True,
        )


if __name__ == "__main__":
    main()
