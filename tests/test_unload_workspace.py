import time
import threading

import pytest
from PyQt6 import QtCore, QtTest
from qt_test_application import application
from test_main_window_characterization import (
    DeterministicCoordinatorRunner,
    FakeExifTool,
    FakePhotoDiscovery,
    FakePhotoIndex,
)

from tagger_app.ui.main_window import MainWindow
from tagger_app.indexing import IndexRefreshProgress


@pytest.fixture
def ui(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path / "settings"))
    monkeypatch.setattr("tagger_app.ui.main_window.ExifTool", FakeExifTool)
    monkeypatch.setattr("tagger_app.ui.main_window.PhotoIndex", FakePhotoIndex)
    FakeExifTool.reset()
    FakePhotoIndex.reset()
    app = application()
    runner = DeterministicCoordinatorRunner()
    discovery = FakePhotoDiscovery()
    window = MainWindow(discovery=discovery, background_runner=runner)
    window.show()
    app.processEvents()

    def wait(condition, *, run_background=True):
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            if run_background:
                runner.run_index_work()
            app.processEvents()
            if condition():
                return
            QtTest.QTest.qWait(10)
        pytest.fail("Timed out waiting for UI outcome")

    yield window, runner, discovery, wait
    FakeExifTool.release_writes()
    window.replace_photo_workspace([])
    assert window.pool.waitForDone(5000)
    app.processEvents()
    window.close()


def command(window, text):
    window.cmdLine.show()
    window.cmdLine.setText(f":{text}")
    QtTest.QTest.keyClick(window.cmdLine, QtCore.Qt.Key.Key_Return)


def test_unload_clears_workspace_filters_details_and_allows_reloading(ui, tmp_path):
    window, runner, discovery, wait = ui
    photo = str(tmp_path / "one.jpg")
    window.add_files([photo])
    wait(lambda: window.keywordsList.count() == 1)
    window.filenameFilterEdit.setText("one")
    window.addEdit.setText("unfinished")
    backup = window.keepBackup.isChecked()

    command(window, "unload")

    assert window.all_file_paths() == []
    assert window.active_file_path() is None
    assert window.files.count() == 0
    assert window.keywordsList.count() == 0
    assert window.dateLabel.text() == ""
    assert window.selectedLabel.text() == "Drop JPG/JPEG files here"
    assert window.filenameFilterEdit.text() == ""
    assert window.addEdit.text() == ""
    assert window.keepBackup.isChecked() == backup
    assert window.statusBar().currentMessage() == "Workspace unloaded"
    window.add_files([photo])
    wait(lambda: window.keywordsList.count() == 1)
    assert window.all_file_paths() == [photo]


@pytest.mark.parametrize("duplicate_review", [False, True])
def test_eject_button_clears_both_views_and_stale_discoveries(
    ui, tmp_path, duplicate_review
):
    window, runner, discovery, wait = ui
    folder = str(tmp_path / "old")
    discovery.results[folder] = [str(tmp_path / "old" / "one.jpg")]
    window.add_dropped_directory(folder)
    if duplicate_review:
        window.show_duplicate_review()
    button = window.duplicateUnloadButton if duplicate_review else window.unloadBtn
    add_folder = (
        window.duplicateAddFolderButton if duplicate_review else window.addFolderBtn
    )
    assert button.height() == add_folder.height()
    assert button.toolTip() == "Unload workspace (:unload)"
    assert button.accessibleName() == "Unload workspace"
    QtTest.QTest.mouseClick(button, QtCore.Qt.MouseButton.LeftButton)
    while runner.scheduled:
        runner.run()
    application().processEvents()
    assert window.files.count() == 0
    assert window.duplicateScopeSizeLabel.text() == "Waiting for a photo folder"
    assert not window.duplicateStartScanButton.isEnabled()
    assert not window.duplicateResultsButton.isVisible()
    assert window.statusBar().currentMessage() == "Workspace unloaded"
    # A new drop must not wait forever for a cancelled earlier drop's sequence.
    next_folder = str(tmp_path / "new")
    photo = str(tmp_path / "new" / "two.jpg")
    discovery.results[next_folder] = [photo]
    window.add_dropped_directory(next_folder)
    while runner.scheduled:
        runner.run()
        application().processEvents()
    assert window.all_file_paths() == [photo]


def test_unload_is_blocked_until_all_tag_writes_finish(ui, tmp_path):
    window, runner, discovery, wait = ui
    photo = str(tmp_path / "one.jpg")
    window.add_files([photo])
    wait(lambda: window.keywordsList.count() == 1)
    FakeExifTool.block_writes()
    window.addEdit.setText("saved")
    window.add_keyword_from_input()
    wait(FakeExifTool.write_started.is_set)
    window.addEdit.setText("also-saved")
    window.add_keyword_from_input()
    assert not window.unloadBtn.isEnabled()
    assert not window.duplicateUnloadButton.isEnabled()
    command(window, "unload")
    assert window.all_file_paths() == [photo]
    assert window.statusBar().currentMessage() == "Wait for tag writes before unloading"
    FakeExifTool.release_writes()
    wait(lambda: window.unloadBtn.isEnabled())
    assert len(FakeExifTool.write_calls) == 2
    command(window, "unload")
    assert window.files.count() == 0


def test_unload_discards_pending_search_and_filter_results(ui, tmp_path):
    window, runner, discovery, wait = ui
    photo = str(tmp_path / "one.jpg")
    window.add_files([photo])
    wait(lambda: window.keywordsList.count() == 1)
    window.dbSearchEdit.setText("confirmed")
    QtTest.QTest.keyClick(window.dbSearchEdit, QtCore.Qt.Key.Key_Return)
    window.onlyUntagged.setChecked(True)
    window.filenameFilterEdit.setText("pending-filter")
    window.directoryExcludeEdit.setText("old")
    command(window, "unload")
    while runner.scheduled:
        runner.run()
    QtTest.QTest.qWait(350)
    assert window.files.count() == 0
    assert window.dbSearchEdit.text() == ""
    assert window.dbDateSearchEdit.text() == ""
    assert window.directoryExcludeEdit.text() == ""
    assert not window.onlyUntagged.isChecked()
    assert window.statusBar().currentMessage() == "Workspace unloaded"


def test_unload_stops_index_discovery_status_animation(ui, tmp_path, monkeypatch):
    window, runner, discovery, wait = ui
    window.add_files([str(tmp_path / "one.jpg")])
    wait(lambda: window.keywordsList.count() == 1)
    runner.run_index_work()
    monkeypatch.setattr(
        FakePhotoIndex,
        "refresh_step",
        lambda index, *args, **kwargs: IndexRefreshProgress(
            root=index.root, phase="discovering", discovered_count=0, indexed_count=0
        ),
        raising=False,
    )
    command(window, "reindex")
    runner.run()
    application().processEvents()
    assert "images for DB index" in window.indexRepairStatusLabel.text()
    command(window, "unload")
    QtTest.QTest.qWait(1200)
    assert window.indexRepairStatusLabel.text() == ""


@pytest.mark.parametrize("repair_finished", [False, True])
def test_unload_ignores_late_missing_search_result_repair(
    ui, tmp_path, repair_finished
):
    window, runner, discovery, wait = ui
    window.add_files([str(tmp_path / "one.jpg")])
    wait(lambda: window.keywordsList.count() == 1)
    FakePhotoIndex.search_results = {str(tmp_path / "missing.jpg")}
    FakeExifTool.metadata_read_error = RuntimeError("File not found")
    window.dbSearchEdit.setText("tag:bird")
    QtTest.QTest.keyClick(window.dbSearchEdit, QtCore.Qt.Key.Key_Return)
    runner.run_index_work()
    wait(
        lambda: window.indexRepairStatusLabel.text().startswith("Index repair queued:"),
        run_background=False,
    )
    if repair_finished:
        # Complete storage work off-thread, leaving its Qt events queued for the UI.
        worker = threading.Thread(target=runner.run_index_work)
        worker.start()
        worker.join(timeout=5)
        assert not worker.is_alive()
    command(window, "unload")
    if not repair_finished:
        # Repeated unload must still protect repair work owned by the coordinator.
        FakeExifTool.metadata_read_error = None
        window.add_files([str(tmp_path / "one.jpg")])
        command(window, "unload")
    runner.run_index_work()
    application().processEvents()
    assert window.indexRepairStatusLabel.text() == ""
    assert window.files.count() == 0
    assert window.statusBar().currentMessage() == "Workspace unloaded"


def test_unload_before_initial_index_sync_allows_loading_same_root_again(ui, tmp_path):
    window, runner, discovery, wait = ui
    photo = str(tmp_path / "one.jpg")
    FakePhotoIndex.snapshot_paths = [photo]
    window.add_files([photo])
    command(window, "unload")
    runner.run_index_work()
    application().processEvents()
    window.add_files([photo])
    window.show_duplicate_review()
    while runner.scheduled:
        runner.run()
        application().processEvents()
    assert window.duplicateStartScanButton.isEnabled()
    assert window.duplicateScopeSizeLabel.text() == "1 photos ready"
