import pytest
from PyQt6 import QtCore, QtWidgets
from test_main_window_characterization import (
    DeterministicCoordinatorRunner,
    FakeExifTool,
    FakePhotoDiscovery,
    FakePhotoIndex,
)

from tagger_app.storage import load_config, save_config
from tagger_app.ui.main_window import MainWindow


@pytest.fixture
def windows(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path / "settings"))
    monkeypatch.setattr("tagger_app.ui.main_window.ExifTool", FakeExifTool)
    monkeypatch.setattr("tagger_app.ui.main_window.PhotoIndex", FakePhotoIndex)
    FakeExifTool.reset()
    FakePhotoIndex.reset()
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    opened = []

    def create():
        window = MainWindow(
            discovery=FakePhotoDiscovery(),
            background_runner=DeterministicCoordinatorRunner(),
        )
        opened.append(window)
        return window

    yield create
    for window in opened:
        assert window.pool.waitForDone(5000)
        window.close()
    app.processEvents()


def configure(window, interact):
    failures = []

    def interact_with_dialog():
        dialog = QtWidgets.QApplication.activeModalWidget()
        try:
            assert dialog.windowTitle() == "Default index root"
            edit = dialog.findChild(QtWidgets.QLineEdit)
            buttons = dialog.findChild(QtWidgets.QDialogButtonBox)
            interact(dialog, edit, buttons)
            assert not dialog.isVisible()
        except BaseException as exc:
            failures.append(exc)
            dialog.reject()

    QtCore.QTimer.singleShot(0, interact_with_dialog)
    window._dispatch_command("indexroot", [])
    if failures:
        raise failures[0]


def click(buttons, button):
    buttons.button(getattr(QtWidgets.QDialogButtonBox.StandardButton, button)).click()


def test_save_browse_restart_and_marker_precedence(windows, tmp_path, monkeypatch):
    library = tmp_path / "Fotos ü"
    nested = library / "album"
    nested.mkdir(parents=True)
    photo = nested / "bird.jpg"
    photo.touch()
    save_config({"last_folder": str(nested), "unrelated": True})
    window = windows()
    window._index_root = "existing-workspace"
    monkeypatch.setattr(
        QtWidgets.QFileDialog, "getExistingDirectory", lambda *args: str(library)
    )

    def save(dialog, edit, buttons):
        next(
            b
            for b in dialog.findChildren(QtWidgets.QPushButton)
            if b.text() == "Browse…"
        ).click()
        assert edit.text() == str(library)
        click(buttons, "Save")

    configure(window, save)
    assert load_config() == {
        "last_folder": str(nested),
        "unrelated": True,
        "default_index_root": str(library.resolve()),
    }
    assert window._index_root == "existing-workspace"
    assert window._index_root_for_paths([]) == "existing-workspace"
    restarted = windows()
    assert restarted._index_root_for_paths([str(photo)]) == str(library.resolve())
    assert restarted._get_default_folder_for_dialog() == str(nested)
    (nested / ".tagger").mkdir()
    assert restarted._index_root_for_paths([str(photo)]) == str(nested.resolve())
    outside = tmp_path / "outside"
    outside.mkdir()
    other = outside / "other.jpg"
    other.touch()
    assert restarted._index_root_for_paths([str(other)]) == str(outside.resolve())


@pytest.mark.parametrize("value", [None, 123, [], "", "relative", "missing", "\x00"])
def test_invalid_setting_falls_back(windows, tmp_path, monkeypatch, value):
    fallback = tmp_path / "Pictures"
    nested = fallback / "album"
    nested.mkdir(parents=True)
    photo = nested / "bird.jpg"
    photo.touch()
    monkeypatch.setattr("tagger_app.ui.main_window.DEFAULT_INDEX_ROOT", fallback)
    save_config({"default_index_root": value})
    window = windows()
    assert window._index_root_for_paths([str(photo)]) == str(fallback)


def test_removed_or_file_setting_falls_back(windows, tmp_path, monkeypatch):
    fallback = tmp_path / "Pictures"
    monkeypatch.setattr("tagger_app.ui.main_window.DEFAULT_INDEX_ROOT", fallback)
    configured = tmp_path / "library"
    configured.mkdir()
    save_config({"default_index_root": str(configured)})
    window = windows()
    assert window._preferred_index_root() == configured
    configured.rmdir()
    assert window._preferred_index_root() == fallback
    configured.touch()
    assert windows()._preferred_index_root() == fallback


def test_cancel_and_restore_default(windows, tmp_path, monkeypatch):
    library = tmp_path / "library"
    library.mkdir()
    fallback = tmp_path / "nonexistent-Pictures"
    monkeypatch.setattr("tagger_app.ui.main_window.DEFAULT_INDEX_ROOT", fallback)
    original = {"default_index_root": str(library), "last_folder": str(library)}
    save_config(original)
    window = windows()

    def cancel(dialog, edit, buttons):
        assert edit.text() == str(library)
        click(buttons, "RestoreDefaults")
        click(buttons, "Cancel")

    configure(window, cancel)
    assert load_config() == original

    def reset(dialog, edit, buttons):
        click(buttons, "RestoreDefaults")
        assert edit.text() == str(fallback)
        click(buttons, "Save")

    window.show_duplicate_review()
    configure(window, reset)
    assert load_config() == {"last_folder": str(library)}
    assert windows()._preferred_index_root() == fallback


def test_invalid_input_and_save_failure_keep_dialog_open(
    windows, tmp_path, monkeypatch
):
    library = tmp_path / "library"
    library.mkdir()
    save_config({"last_folder": str(library)})
    window = windows()

    def fail_save(config):
        raise OSError("disk full")

    monkeypatch.setattr("tagger_app.ui.main_window.save_config", fail_save)

    def invalid(dialog, edit, buttons):
        edit.setText(str(tmp_path / "missing"))
        click(buttons, "Save")
        assert dialog.isVisible()
        assert any(
            "existing folder" in label.text()
            for label in dialog.findChildren(QtWidgets.QLabel)
        )
        edit.setText(str(library))
        click(buttons, "Save")
        assert dialog.isVisible()
        assert any(
            "disk full" in label.text()
            for label in dialog.findChildren(QtWidgets.QLabel)
        )
        click(buttons, "Cancel")

    configure(window, invalid)
    assert load_config() == {"last_folder": str(library)}
    assert "default_index_root" not in window._config
