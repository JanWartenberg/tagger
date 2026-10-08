import time
from pathlib import Path

import pytest
from PyQt6 import QtCore, QtTest, QtWidgets
from test_main_window_characterization import (
    DeterministicCoordinatorRunner,
    FakeExifTool,
    FakePhotoDiscovery,
    FakePhotoIndex,
)

from tagger_app.exif_tool import KeywordState
from tagger_app.ui.main_window import MainWindow


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path / "settings"))
    monkeypatch.setattr("tagger_app.ui.main_window.ExifTool", FakeExifTool)
    monkeypatch.setattr("tagger_app.ui.main_window.PhotoIndex", FakePhotoIndex)
    FakeExifTool.reset()
    FakePhotoIndex.reset()
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    paths = [str(tmp_path / name) for name in ("source.jpg", "target.jpg")]
    FakePhotoIndex.snapshot_paths = paths
    FakeExifTool.states_by_path = {
        paths[0]: KeywordState(["Holiday"], [], "2024:01:02 03:04:05"),
        paths[1]: KeywordState([], [], "2024:01:02 03:04:05"),
    }
    opened = []

    def create():
        runner = DeterministicCoordinatorRunner()
        window = MainWindow(discovery=FakePhotoDiscovery(), background_runner=runner)
        window._index_root = str(tmp_path)
        window.show()
        window.show_duplicate_review()
        runner.run()
        app.processEvents()
        opened.append((window, runner))
        return window, runner

    yield create, app, paths
    for window, runner in opened:
        while runner.scheduled:
            runner.run()
        app.processEvents()
        assert window.pool.waitForDone(5000)
        app.processEvents()
        window.close()
    app.processEvents()


def scan(window, runner, app):
    window.duplicateStartScanButton.click()
    runner.run()
    app.processEvents()


def wait(app, runner, predicate):
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        while runner.scheduled:
            runner.run()
        app.processEvents()
        if predicate():
            return
        QtTest.QTest.qWait(10)
    pytest.fail("Timed out waiting for ignored candidate controls")


def test_ignore_restart_inspect_without_restore_and_explicit_restore(workspace):
    create, app, _paths = workspace
    window, runner = create()
    scan(window, runner, app)
    window.duplicateIgnoreButton.click()
    wait(app, runner, lambda: "remembered" in window.statusBar().currentMessage())
    assert not window.duplicateCandidateQueue.isVisible()

    restarted, runner = create()
    scan(restarted, runner, app)
    assert not restarted.duplicateCandidateQueue.isVisible()
    restarted.duplicateIgnoredCandidatesButton.click()
    wait(app, runner, lambda: app.activeModalWidget() is not None)
    dialog = app.activeModalWidget()
    candidates = dialog.findChild(QtWidgets.QListWidget)
    wait(app, runner, lambda: candidates.count() == 1)
    assert "2024:01:02" in candidates.item(0).text()
    assert "Holiday" in " ".join(
        label.text() for label in dialog.findChildren(QtWidgets.QLabel)
    )
    dialog.reject()
    scan(restarted, runner, app)
    assert not restarted.duplicateCandidateQueue.isVisible()

    restarted.duplicateIgnoredCandidatesButton.click()
    wait(
        app,
        runner,
        lambda: app.activeModalWidget().findChild(QtWidgets.QListWidget).count() == 1,
    )
    dialog = app.activeModalWidget()
    next(
        button
        for button in dialog.findChildren(QtWidgets.QPushButton)
        if button.text().replace("&", "") == "Restore"
    ).click()
    wait(app, runner, lambda: dialog.findChild(QtWidgets.QListWidget).count() == 0)
    dialog.reject()
    assert restarted.duplicateCandidateQueue.isVisible()
    scan(restarted, runner, app)
    assert restarted.duplicateCandidateQueue.isVisible()
    assert FakeExifTool.write_calls == []


def test_tag_changes_stay_ignored_but_changed_capture_evidence_returns(workspace):
    create, app, paths = workspace
    window, runner = create()
    scan(window, runner, app)
    window.duplicateIgnoreButton.click()
    wait(app, runner, lambda: "remembered" in window.statusBar().currentMessage())
    FakeExifTool.states_by_path[paths[0]] = KeywordState(
        ["Different tags"], [], "2024:01:02 03:04:05"
    )
    scan(window, runner, app)
    assert not window.duplicateCandidateQueue.isVisible()
    for path in paths:
        old = FakeExifTool.states_by_path[path]
        FakeExifTool.states_by_path[path] = KeywordState(
            old.iptc, old.xmp, None, "2024:01:02 03:04:05"
        )
    scan(window, runner, app)
    assert window.duplicateCandidateQueue.isVisible()


def test_clear_requires_confirmation_and_restores_review(workspace, monkeypatch):
    create, app, _paths = workspace
    window, runner = create()
    scan(window, runner, app)
    window.duplicateIgnoreButton.click()
    wait(app, runner, lambda: "remembered" in window.statusBar().currentMessage())
    window.duplicateIgnoredCandidatesButton.click()
    wait(
        app,
        runner,
        lambda: app.activeModalWidget().findChild(QtWidgets.QListWidget).count() == 1,
    )
    dialog = app.activeModalWidget()
    clear = next(
        button
        for button in dialog.findChildren(QtWidgets.QPushButton)
        if button.text().replace("&", "") == "Clear all ignores…"
    )
    monkeypatch.setattr(
        QtWidgets.QMessageBox,
        "question",
        lambda *args, **kwargs: QtWidgets.QMessageBox.StandardButton.No,
    )
    clear.click()
    assert dialog.findChild(QtWidgets.QListWidget).count() == 1
    assert not window.duplicateCandidateQueue.isVisible()
    monkeypatch.setattr(
        QtWidgets.QMessageBox,
        "question",
        lambda *args, **kwargs: QtWidgets.QMessageBox.StandardButton.Yes,
    )
    clear.click()
    wait(app, runner, lambda: dialog.findChild(QtWidgets.QListWidget).count() == 0)
    dialog.reject()
    assert window.duplicateCandidateQueue.isVisible()


def test_failed_ignore_keeps_candidate_visible_and_reports_error(workspace):
    create, app, paths = workspace
    window, runner = create()
    scan(window, runner, app)
    # A filesystem obstacle exercises the real persistence boundary.
    (Path(paths[0]).parent / ".tagger").write_text("not a directory")
    window.duplicateIgnoreButton.click()
    assert not window.duplicateStartScanButton.isEnabled()
    assert not window.duplicateIgnoreButton.isEnabled()
    wait(
        app,
        runner,
        lambda: "Could not update ignored candidates"
        in window.statusBar().currentMessage(),
    )
    assert window.duplicateCandidateQueue.isVisible()
    assert window.duplicateIgnoreButton.isEnabled()
    assert not window.duplicateResultsButton.isVisible()


def test_close_list_before_loading_finishes_is_safe(workspace):
    create, app, _paths = workspace
    window, runner = create()
    window.duplicateIgnoredCandidatesButton.click()
    dialog = app.activeModalWidget()
    assert dialog is not None
    dialog.reject()
    wait(app, runner, lambda: window.duplicateIgnoredCandidatesButton.isEnabled())
    assert app.activeModalWidget() is None


def test_ctrl_i_opens_ignored_candidates_with_collapsed_setup_and_is_view_scoped(
    workspace,
):
    create, app, _paths = workspace
    window, runner = create()
    assert "Ctrl+I" in window.duplicateIgnoredCandidatesButton.toolTip()
    window.duplicateScanSetupToggle.click()
    window.duplicateScanSetupToggle.setFocus()
    QtTest.QTest.keyClick(
        window.focusWidget(),
        QtCore.Qt.Key.Key_I,
        QtCore.Qt.KeyboardModifier.ControlModifier,
    )
    wait(app, runner, lambda: app.activeModalWidget() is not None)
    dialog = app.activeModalWidget()
    assert dialog.windowTitle() == "Ignored candidates"
    wait(
        app,
        runner,
        lambda: "No ignored candidates"
        in " ".join(label.text() for label in dialog.findChildren(QtWidgets.QLabel)),
    )
    dialog.reject()
    app.processEvents()
    window.show_tagging_workspace()
    QtTest.QTest.keyClick(
        window.files, QtCore.Qt.Key.Key_I, QtCore.Qt.KeyboardModifier.ControlModifier
    )
    app.processEvents()
    assert app.activeModalWidget() is None


def test_ignored_list_keyboard_navigation_restore_and_close(workspace):
    from tagger_app.services.duplicate_detection import CandidateGroup, CandidateMember
    from tagger_app.services.ignored_candidates import IgnoredCandidateStore

    create, app, paths = workspace
    store = IgnoredCandidateStore(Path(paths[0]).parent)
    for day in (1, 2, 3):
        store.remember(
            "same-capture-timestamp",
            CandidateGroup(
                str(day),
                tuple(
                    CandidateMember(
                        path, f"2024:01:{day:02} 12:00:00", "EXIF:DateTimeOriginal"
                    )
                    for path in paths
                ),
            ),
        )
    window, runner = create()
    window.duplicateIgnoredCandidatesButton.click()
    wait(
        app,
        runner,
        lambda: app.activeModalWidget().findChild(QtWidgets.QListWidget).count() == 3,
    )
    dialog = app.activeModalWidget()
    candidates = dialog.findChild(QtWidgets.QListWidget)
    candidates.setFocus()
    assert candidates.currentRow() == 0
    QtTest.QTest.keyClick(candidates, QtCore.Qt.Key.Key_J)
    assert candidates.currentRow() == 1
    QtTest.QTest.keyClick(candidates, QtCore.Qt.Key.Key_K)
    assert candidates.currentRow() == 0
    QtTest.QTest.keyClick(candidates, QtCore.Qt.Key.Key_K)
    assert candidates.currentRow() == 0
    QtTest.QTest.keyClick(candidates, QtCore.Qt.Key.Key_J)
    selected = candidates.currentItem().text()
    QtTest.QTest.keyClick(candidates, QtCore.Qt.Key.Key_R)
    wait(app, runner, lambda: candidates.count() == 2)
    assert selected not in [
        candidates.item(i).text() for i in range(candidates.count())
    ]
    buttons = {
        button.text(): button for button in dialog.findChildren(QtWidgets.QPushButton)
    }
    for text, shortcut in (
        ("&Restore", "r"),
        ("Clear &all ignores…", "a"),
        ("&Close", "c"),
    ):
        assert text in buttons
        assert shortcut in buttons[text].toolTip()
    QtTest.QTest.keyClick(candidates, QtCore.Qt.Key.Key_C)
    app.processEvents()
    assert app.activeModalWidget() is None
    assert len(store.list()) == 2
    assert FakeExifTool.write_calls == []


def test_ignored_list_keyboard_clear_keeps_confirmation_and_escape_close(
    workspace, monkeypatch
):
    create, app, _paths = workspace
    window, runner = create()
    scan(window, runner, app)
    window.duplicateIgnoreButton.click()
    wait(app, runner, lambda: "remembered" in window.statusBar().currentMessage())
    window.duplicateIgnoredCandidatesButton.click()
    wait(
        app,
        runner,
        lambda: app.activeModalWidget().findChild(QtWidgets.QListWidget).count() == 1,
    )
    dialog = app.activeModalWidget()
    candidates = dialog.findChild(QtWidgets.QListWidget)
    monkeypatch.setattr(
        QtWidgets.QMessageBox,
        "question",
        lambda *args, **kwargs: QtWidgets.QMessageBox.StandardButton.No,
    )
    QtTest.QTest.keyClick(candidates, QtCore.Qt.Key.Key_A)
    assert candidates.count() == 1
    monkeypatch.setattr(
        QtWidgets.QMessageBox,
        "question",
        lambda *args, **kwargs: QtWidgets.QMessageBox.StandardButton.Yes,
    )
    QtTest.QTest.keyClick(candidates, QtCore.Qt.Key.Key_A)
    wait(app, runner, lambda: candidates.count() == 0)
    for key in (QtCore.Qt.Key.Key_J, QtCore.Qt.Key.Key_K, QtCore.Qt.Key.Key_R):
        QtTest.QTest.keyClick(candidates, key)
    assert candidates.currentRow() == -1
    QtTest.QTest.keyClick(candidates, QtCore.Qt.Key.Key_Escape)
    app.processEvents()
    assert app.activeModalWidget() is None


def test_shortcut_underlines_are_visible_before_alt(workspace):
    class HiddenMnemonicsStyle(QtWidgets.QProxyStyle):
        def styleHint(self, hint, option=None, widget=None, returnData=None):
            if hint == QtWidgets.QStyle.StyleHint.SH_UnderlineShortcut:
                return 0
            return super().styleHint(hint, option, widget, returnData)

    create, app, _paths = workspace
    original_style = app.style().objectName()
    app.setStyle(HiddenMnemonicsStyle("Fusion"))
    window = None
    try:
        window, runner = create()
        window.duplicateIgnoredCandidatesButton.click()
        wait(app, runner, lambda: app.activeModalWidget() is not None)
        dialog = app.activeModalWidget()
        hint = QtWidgets.QStyle.StyleHint.SH_UnderlineShortcut
        assert not window.duplicateIgnoredCandidatesButton.style().styleHint(hint)
        buttons = dialog.findChildren(QtWidgets.QPushButton)
        assert len(buttons) == 3
        for button in buttons:
            option = QtWidgets.QStyleOptionButton()
            button.initStyleOption(option)
            assert button.style().styleHint(hint, option, button)
        dialog.reject()
        app.processEvents()
    finally:
        if app.activeModalWidget() is not None:
            app.activeModalWidget().reject()
        app.processEvents()
        app.setStyle(original_style)
