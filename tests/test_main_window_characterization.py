"""Windows/offscreen characterization tests for the current Qt adapter.

These tests deliberately exercise public MainWindow entrypoints and widgets.  They
are a behavior baseline for the Photo Workspace refactor, not tests of private
state or rendering details.
"""

from __future__ import annotations

import os
import tempfile
import threading
import time
import unittest
from collections.abc import Callable
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PyQt6 import QtCore, QtTest, QtWidgets
except ModuleNotFoundError:
    PYQT_AVAILABLE = False
else:
    PYQT_AVAILABLE = True

if PYQT_AVAILABLE:
    from exif_tool import KeywordState
    from exif_ui import MainWindow
    from services.background_coordinator import (
        IndexEnsureCompleted,
        IndexWriteFailed,
        IndexOperationKind,
    )
    from utils import normalize_path


@unittest.skipUnless(
    PYQT_AVAILABLE, "PyQt6 is required for Qt adapter characterization tests"
)
class MainWindowCharacterizationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def setUp(self) -> None:
        self.exif_patch = patch("exif_ui.ExifTool", FakeExifTool)
        self.index_patch = patch("exif_ui.PhotoIndex", FakePhotoIndex)
        self.exif_patch.start()
        self.index_patch.start()
        self.addCleanup(self.index_patch.stop)
        self.addCleanup(self.exif_patch.stop)
        FakeExifTool.reset()
        FakePhotoIndex.reset()
        self.discovery = FakePhotoDiscovery()
        self.discovery_runner = DeterministicCoordinatorRunner()
        self.window = MainWindow(
            discovery=self.discovery,
            background_runner=self.discovery_runner,
        )
        self.window.show()
        self.window.activateWindow()
        self.app.processEvents()
        self.addCleanup(self._close_window)

    def _close_window(self) -> None:
        FakeExifTool.release_writes()
        self.window.pool.waitForDone(2000)
        self.app.processEvents()
        self.window.close()

    def _add_paths(self, *names: str) -> list[str]:
        paths = [str(Path("C:/photos") / name) for name in names]
        self.window.add_files(paths)
        self.discovery_runner.run_index_work()
        self.app.processEvents()
        return [normalize_path(path) for path in paths]

    def _wait_until(self, condition) -> None:
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            self.discovery_runner.run_index_work()
            self.app.processEvents()
            if condition():
                self.discovery_runner.run_index_work()
                self.app.processEvents()
                return
            QtTest.QTest.qWait(10)
        self.fail("Timed out waiting for asynchronous UI work")

    def _choose_folder(self, folder: str) -> None:
        with patch(
            "exif_ui.QtWidgets.QFileDialog.getExistingDirectory", return_value=folder
        ):
            self.window.add_folder_dialog()

    def test_view_indicator_describes_the_normal_photo_workspace(self) -> None:
        self.assertEqual(self.window.filterInfoLabel.text(), "Folder view · 0 photos")

        self._add_paths("first.jpg", "second.jpg")

        self.assertEqual(self.window.filterInfoLabel.text(), "Folder view · 2 photos")

    def test_view_indicator_describes_pending_and_completed_iptc_empty_filter(
        self,
    ) -> None:
        self._add_paths("first.jpg", "second.jpg")

        self.window.onlyUntagged.setChecked(True)

        self.assertEqual(
            self.window.filterInfoLabel.text(), "Filtering IPTC-empty · 0/2"
        )
        self._wait_until(self.window.onlyUntagged.isChecked)
        self.assertEqual(self.window.filterInfoLabel.text(), "IPTC-empty · 0/2")

        self.window.onlyUntagged.setChecked(False)

        self.assertEqual(self.window.filterInfoLabel.text(), "Folder view · 2 photos")

    def test_view_indicator_describes_pending_and_completed_search_and_back(
        self,
    ) -> None:
        _first, second = self._add_paths("first.jpg", "second.jpg")
        FakePhotoIndex.search_results = {second}
        self.window.dbSearchEdit.setText("tag:second")

        self.window.apply_db_search()

        self.assertEqual(
            self.window.filterInfoLabel.text(), "Searching index · tag:second"
        )
        self.discovery_runner.run_index_work()
        self.app.processEvents()
        self.assertEqual(
            self.window.filterInfoLabel.text(),
            "Search: tag:second · 1 results · :back",
        )

        self.window._dispatch_command("back", [])

        self.assertEqual(self.window.filterInfoLabel.text(), "Folder view · 2 photos")

    def test_entering_a_search_moves_focus_to_the_first_result(self) -> None:
        _first, second = self._add_paths("first.jpg", "second.jpg")
        FakePhotoIndex.search_results = {second}
        self.window.dbSearchEdit.setText("tag:second")
        self.window.dbSearchEdit.setFocus()

        QtTest.QTest.keyClick(self.window.dbSearchEdit, QtCore.Qt.Key.Key_Return)
        self.discovery_runner.run_index_work()
        self.app.processEvents()

        self.assertEqual(self.window.selected_file_paths(), [second])
        self.assertIs(self.window.focusWidget(), self.window.files)

    def test_view_indicator_restores_folder_scope_after_a_failed_search(self) -> None:
        self._add_paths("first.jpg", "second.jpg")
        self.window.dbSearchEdit.setText("tag:missing")

        with patch.object(
            FakePhotoIndex, "search_photos", side_effect=RuntimeError("index failed")
        ):
            self.window.apply_db_search()
            self.discovery_runner.run_index_work()
            self.app.processEvents()

        self.assertEqual(self.window.filterInfoLabel.text(), "Folder view · 2 photos")

    def test_view_indicator_restores_folder_scope_when_replacing_the_workspace(
        self,
    ) -> None:
        self._add_paths("first.jpg", "second.jpg")
        replacement = normalize_path("C:/photos/replacement.jpg")

        self.window.replace_photo_workspace([replacement])

        self.assertEqual(self.window.filterInfoLabel.text(), "Folder view · 1 photos")

    def test_folder_discovery_clears_the_workspace_and_renders_paths_on_completion(
        self,
    ) -> None:
        (old_path,) = self._add_paths("old.jpg")
        folder = "/replacement"
        self.discovery.results[folder] = [f"{folder}/one.jpg"]

        self._choose_folder(folder)

        self.assertEqual(self.window.all_file_paths(), [])
        self.assertEqual(self.window.files.count(), 0)
        self.assertTrue(self.window.filesPaneMessage.isVisible())
        self.assertEqual(self.window.filesPaneMessage.text(), "Loading photos…")
        self.assertNotEqual(self.window.selectedLabel.text(), old_path)

        self.discovery_runner.run_discovery()
        (loaded_path,) = [normalize_path(f"{folder}/one.jpg")]
        self.assertEqual(self.window.all_file_paths(), [loaded_path])
        self.assertEqual(self.window.selected_file_paths(), [loaded_path])
        self.assertFalse(self.window.filesPaneMessage.isVisible())

    def test_stale_folder_discovery_cannot_replace_a_newer_workspace(self) -> None:
        first = "/first"
        second = "/second"
        self.discovery.results[first] = [f"{first}/one.jpg"]
        self.discovery.results[second] = [f"{second}/two.jpg"]

        self._choose_folder(first)
        self._choose_folder(second)
        self.discovery_runner.run_discovery()
        self.assertEqual(self.window.all_file_paths(), [])

        self.discovery_runner.run_discovery()
        self.assertEqual(
            self.window.all_file_paths(), [normalize_path(f"{second}/two.jpg")]
        )

    def test_dropped_directory_keeps_the_current_selection_until_it_appends(
        self,
    ) -> None:
        first, second = self._add_paths("one.jpg", "two.jpg")
        self.window.files.setCurrentItem(
            self.window.files.item(1),
            QtCore.QItemSelectionModel.SelectionFlag.ClearAndSelect,
        )
        self.app.processEvents()
        with tempfile.TemporaryDirectory() as folder:
            normalized_folder = normalize_path(folder)
            self.discovery.results[normalized_folder] = [
                f"{normalized_folder}/three.jpg"
            ]

            self.window.handle_dropped_urls([QtCore.QUrl.fromLocalFile(folder)])

            self.assertEqual(self.window.selected_file_paths(), [second])
            self.assertEqual(
                self.window.statusBar().currentMessage(), "Loading photos…"
            )

            self.discovery_runner.run_discovery()
            self.assertEqual(
                self.window.all_file_paths(),
                [first, second, normalize_path(f"{normalized_folder}/three.jpg")],
            )
            self.assertEqual(self.window.selected_file_paths(), [second])

    def test_dropped_directories_append_in_drop_initiation_order(self) -> None:
        (existing,) = self._add_paths("existing.jpg")
        first = "/first-drop"
        second = "/second-drop"
        self.discovery.results[first] = [f"{first}/one.jpg"]
        self.discovery.results[second] = [f"{second}/two.jpg"]

        self.window.add_dropped_directory(first)
        self.window.add_dropped_directory(second)
        self.discovery_runner.run_discovery(1)
        self.assertEqual(self.window.all_file_paths(), [existing])

        self.discovery_runner.run_discovery()
        self.assertEqual(
            self.window.all_file_paths(),
            [
                existing,
                normalize_path(f"{first}/one.jpg"),
                normalize_path(f"{second}/two.jpg"),
            ],
        )

    def test_failed_folder_discovery_uses_footer_feedback_without_a_modal(self) -> None:
        folder = "/broken"
        self.discovery.results[folder] = RuntimeError("discovery failed")

        self._choose_folder(folder)
        with patch("exif_ui.QtWidgets.QMessageBox.critical") as critical:
            self.discovery_runner.run_discovery()

        self.assertEqual(self.window.all_file_paths(), [])
        self.assertTrue(self.window.filesPaneMessage.isVisible())
        self.assertEqual(self.window.filesPaneMessage.text(), "No photos loaded")
        self.assertIn("Loading photos failed", self.window.statusBar().currentMessage())
        critical.assert_not_called()

    def test_stale_index_events_do_not_replace_current_footer_feedback(self) -> None:
        self._add_paths("one.jpg")
        self.window.statusBar().showMessage("Searching index…")

        self.window.backgroundDiscoveryEvent.emit(
            IndexEnsureCompleted(root="/stale", result=None)
        )
        self.app.processEvents()

        self.assertEqual(self.window.statusBar().currentMessage(), "Searching index…")

    def test_current_index_failure_uses_footer_feedback_without_a_modal(self) -> None:
        self._add_paths("one.jpg")
        root = self.window._index_root
        self.assertIsNotNone(root)

        with patch("exif_ui.QtWidgets.QMessageBox.critical") as critical:
            self.window.backgroundDiscoveryEvent.emit(
                IndexWriteFailed(
                    root=root,
                    operation=IndexOperationKind.UPDATE_STATES,
                    error="index failed",
                )
            )
            self.app.processEvents()

        self.assertEqual(
            self.window.statusBar().currentMessage(), "Index update failed"
        )
        critical.assert_not_called()

    def test_backups_are_disabled_by_default(self) -> None:
        self.assertFalse(self.window.keepBackup.isChecked())

    def test_failed_single_photo_tag_write_restores_confirmed_tags_and_marks_the_photo(
        self,
    ) -> None:
        (path,) = self._add_paths("one.jpg")
        self._wait_until(lambda: self.window.keywordsList.count() == 1)
        FakeExifTool.block_writes()
        FakeExifTool.fail_writes = True

        self.window.addEdit.setText("pending")
        self.window.add_keyword_from_input()
        self._wait_until(FakeExifTool.write_started.is_set)

        item = next(
            item
            for item in (
                self.window.files.item(index)
                for index in range(self.window.files.count())
            )
            if item is not None and item.text() == path
        )
        self.assertFalse(item.icon().isNull())
        self.assertIn("Saving", self.window.mutationStatusLabel.text())
        self.assertEqual(
            [
                self.window.keywordsList.item(i).text()
                for i in range(self.window.keywordsList.count())
            ],
            ["confirmed", "pending"],
        )
        self.assertTrue(self.window.addEdit.isEnabled())

        with patch("exif_ui.QtWidgets.QMessageBox.critical"):
            FakeExifTool.release_writes()
            self._wait_until(
                lambda: "attention" in self.window.mutationStatusLabel.text()
            )

        self.assertFalse(item.icon().isNull())
        self.assertEqual(
            item.toolTip(), "Tag changes need attention; retry with :retry"
        )
        self.assertEqual(
            [
                self.window.keywordsList.item(i).text()
                for i in range(self.window.keywordsList.count())
            ],
            ["confirmed"],
        )

    def test_successful_single_photo_tag_write_confirms_and_clears_the_pending_marker(
        self,
    ) -> None:
        (path,) = self._add_paths("one.jpg")
        self._wait_until(lambda: self.window.keywordsList.count() == 1)
        FakeExifTool.block_writes()

        self.window.addEdit.setText("pending")
        self.window.add_keyword_from_input()
        self._wait_until(FakeExifTool.write_started.is_set)

        item = self.window.files.item(0)
        self.assertFalse(item.icon().isNull())
        self.assertIn("Saving", self.window.mutationStatusLabel.text())
        self.assertEqual(FakePhotoIndex.states_by_path[path].merged, ["confirmed"])

        FakeExifTool.release_writes()
        self._wait_until(lambda: self.window.mutationStatusLabel.text() == "")

        self.assertTrue(item.icon().isNull())
        self.assertEqual(
            FakePhotoIndex.states_by_path[path].merged,
            ["confirmed", "pending"],
        )
        self.assertEqual(
            [
                self.window.keywordsList.item(i).text()
                for i in range(self.window.keywordsList.count())
            ],
            ["confirmed", "pending"],
        )
        self.assertEqual(path, self.window.selected_file_paths()[0])

    def test_detail_status_tracks_the_current_photo_while_another_photo_is_pending(
        self,
    ) -> None:
        first, second = self._add_paths("one.jpg", "two.jpg")
        self._wait_until(lambda: self.window.keywordsList.count() == 1)
        FakeExifTool.block_writes()

        self.window.addEdit.setText("pending")
        self.window.add_keyword_from_input()
        self._wait_until(FakeExifTool.write_started.is_set)
        self.assertIn("Saving", self.window.mutationStatusLabel.text())

        self.window.files.setCurrentItem(
            self.window.files.item(1),
            QtCore.QItemSelectionModel.SelectionFlag.ClearAndSelect,
        )
        self.app.processEvents()

        self.assertEqual(self.window.selected_file_paths(), [second])
        self.assertEqual(self.window.mutationStatusLabel.text(), "")
        self.assertNotEqual(first, second)

    def test_partial_batch_marks_only_failed_photo_and_retry_resubmits_only_it(
        self,
    ) -> None:
        first, second = self._add_paths("one.jpg", "two.jpg")
        self._wait_until(lambda: self.window.keywordsList.count() == 1)
        self.window.files.setCurrentItem(
            self.window.files.item(0),
            QtCore.QItemSelectionModel.SelectionFlag.ClearAndSelect,
        )
        self.window.files.selectionModel().select(
            self.window.files.model().index(1, 0),
            QtCore.QItemSelectionModel.SelectionFlag.Select,
        )
        self.app.processEvents()
        self.assertEqual(self.window.selected_file_paths(), [first, second])
        FakeExifTool.write_failures = [False, True]

        self.window.addEdit.setText("added")
        self.window.add_keyword_from_input()
        self._wait_until(lambda: len(FakeExifTool.write_calls) == 2)
        self._wait_until(lambda: not self.window.files.item(1).icon().isNull())

        self.assertTrue(self.window.files.item(0).icon().isNull())
        self.assertEqual(
            FakePhotoIndex.states_by_path[first].merged, ["added", "confirmed"]
        )
        self.assertNotIn(second, FakePhotoIndex.states_by_path)
        self.assertIn("1 succeeded, 1 failed", self.window.statusBar().currentMessage())

        self.window.files.setCurrentItem(
            self.window.files.item(1),
            QtCore.QItemSelectionModel.SelectionFlag.ClearAndSelect,
        )
        self.app.processEvents()
        self.assertIn("attention", self.window.mutationStatusLabel.text())

        self.window._dispatch_command("retry", [])
        self._wait_until(lambda: len(FakeExifTool.write_calls) == 3)
        self._wait_until(lambda: self.window.files.item(1).icon().isNull())

        self.assertEqual(FakeExifTool.write_calls[2], (second, ["added", "confirmed"]))
        self.assertEqual(
            len([path for path, _tags in FakeExifTool.write_calls if path == first]), 1
        )
        self.assertEqual(
            FakePhotoIndex.states_by_path[second].merged, ["added", "confirmed"]
        )

    def test_retryall_retries_all_failed_photos_but_not_pending_ones(self) -> None:
        first, second, pending = self._add_paths("one.jpg", "two.jpg", "three.jpg")
        self._wait_until(lambda: self.window.keywordsList.count() == 1)
        self.window.files.setCurrentItem(
            self.window.files.item(0),
            QtCore.QItemSelectionModel.SelectionFlag.ClearAndSelect,
        )
        self.window.files.selectionModel().select(
            self.window.files.model().index(1, 0),
            QtCore.QItemSelectionModel.SelectionFlag.Select,
        )
        self.app.processEvents()
        FakeExifTool.write_failures = [True, True]

        self.window.addEdit.setText("added")
        self.window.add_keyword_from_input()
        self._wait_until(lambda: len(FakeExifTool.write_calls) == 2)
        self._wait_until(lambda: not self.window.files.item(1).icon().isNull())

        self.window.files.setCurrentItem(
            self.window.files.item(2),
            QtCore.QItemSelectionModel.SelectionFlag.ClearAndSelect,
        )
        FakeExifTool.block_writes()
        self.window.addEdit.setText("still-pending")
        self.window.add_keyword_from_input()
        self._wait_until(lambda: len(FakeExifTool.write_calls) == 3)

        self.window._dispatch_command("retryall", [])
        FakeExifTool.release_writes()
        self._wait_until(lambda: len(FakeExifTool.write_calls) == 5)
        self._wait_until(lambda: self.window.files.item(0).icon().isNull())
        self._wait_until(lambda: self.window.files.item(1).icon().isNull())
        self._wait_until(lambda: self.window.files.item(2).icon().isNull())

        self.assertEqual(
            [path for path, _tags in FakeExifTool.write_calls[3:]], [first, second]
        )
        self.assertEqual(
            len([path for path, _tags in FakeExifTool.write_calls if path == pending]),
            1,
        )

    def test_retryall_excludes_failed_mutations_outside_the_current_workspace(
        self,
    ) -> None:
        (departed,) = self._add_paths("departed.jpg")
        self._wait_until(lambda: self.window.keywordsList.count() == 1)
        FakeExifTool.write_failures = [True]
        self.window.addEdit.setText("departed-failure")
        self.window.add_keyword_from_input()
        self._wait_until(lambda: len(FakeExifTool.write_calls) == 1)
        self._wait_until(lambda: not self.window.files.item(0).icon().isNull())

        replacement = normalize_path(str(Path("C:/photos") / "replacement.jpg"))
        self.window.replace_photo_workspace([replacement])
        self._wait_until(lambda: self.window.selected_file_paths() == [replacement])
        self._wait_until(lambda: self.window.keywordsList.count() == 1)
        FakeExifTool.write_failures = [True]
        self.window.addEdit.setText("replacement-failure")
        self.window.add_keyword_from_input()
        self._wait_until(lambda: len(FakeExifTool.write_calls) == 2)
        self._wait_until(lambda: not self.window.files.item(0).icon().isNull())

        self.window._dispatch_command("retryall", [])
        self._wait_until(lambda: len(FakeExifTool.write_calls) == 3)
        self._wait_until(lambda: self.window.files.item(0).icon().isNull())

        self.assertEqual(
            [path for path, _tags in FakeExifTool.write_calls],
            [departed, replacement, replacement],
        )

    def test_returned_photo_shows_session_only_unresolved_attention(self) -> None:
        (departed,) = self._add_paths("departed.jpg")
        self._wait_until(lambda: self.window.keywordsList.count() == 1)
        FakeExifTool.write_failures = [True]
        self.window.addEdit.setText("unresolved")
        self.window.add_keyword_from_input()
        self._wait_until(lambda: len(FakeExifTool.write_calls) == 1)
        self._wait_until(lambda: not self.window.files.item(0).icon().isNull())

        replacement = normalize_path(str(Path("C:/photos") / "replacement.jpg"))
        self.window.replace_photo_workspace([replacement])
        self._wait_until(lambda: self.window.selected_file_paths() == [replacement])
        self.assertTrue(self.window.files.item(0).icon().isNull())

        self.window.replace_photo_workspace([departed])
        self._wait_until(lambda: self.window.selected_file_paths() == [departed])
        self._wait_until(lambda: not self.window.files.item(0).icon().isNull())

        self.assertEqual(
            self.window.files.item(0).toolTip(),
            "Tag changes need attention; retry with :retry",
        )
        self.assertIn("attention", self.window.mutationStatusLabel.text())

    def test_workspace_replacement_discards_queued_writes_and_ignores_inflight_ui_completion(
        self,
    ) -> None:
        (departed,) = self._add_paths("departed.jpg")
        self._wait_until(lambda: self.window.keywordsList.count() == 1)
        FakeExifTool.block_writes()

        self.window.addEdit.setText("inflight")
        self.window.add_keyword_from_input()
        self._wait_until(FakeExifTool.write_started.is_set)
        self.window.addEdit.setText("discarded")
        self.window.add_keyword_from_input()

        replacement = normalize_path(str(Path("C:/photos") / "replacement.jpg"))
        self.window.replace_photo_workspace([replacement])
        self._wait_until(lambda: self.window.selected_file_paths() == [replacement])
        self._wait_until(lambda: self.window.keywordsList.count() == 1)

        FakeExifTool.release_writes()
        self._wait_until(
            lambda: FakePhotoIndex.states_by_path.get(
                departed, KeywordState([], [])
            ).merged
            == ["confirmed", "inflight"]
        )

        self.assertEqual(len(FakeExifTool.write_calls), 1)
        self.assertEqual(
            FakePhotoIndex.states_by_path[departed].merged, ["confirmed", "inflight"]
        )
        self.assertEqual(self.window.all_file_paths(), [replacement])
        self.assertEqual(self.window.selected_file_paths(), [replacement])
        self.assertEqual(
            [
                self.window.keywordsList.item(index).text()
                for index in range(self.window.keywordsList.count())
            ],
            ["confirmed"],
        )

    def test_workspace_replacement_keeps_queued_writes_for_photos_that_remain(
        self,
    ) -> None:
        departed, remaining = self._add_paths("departed.jpg", "remaining.jpg")
        self._wait_until(lambda: self.window.keywordsList.count() == 1)
        FakeExifTool.block_writes()

        self.window.addEdit.setText("inflight")
        self.window.add_keyword_from_input()
        self._wait_until(FakeExifTool.write_started.is_set)
        self.window.files.setCurrentItem(
            self.window.files.item(1),
            QtCore.QItemSelectionModel.SelectionFlag.ClearAndSelect,
        )
        self.window.addEdit.setText("queued")
        self.window.add_keyword_from_input()

        self.window.replace_photo_workspace([remaining])
        FakeExifTool.release_writes()
        self._wait_until(lambda: len(FakeExifTool.write_calls) == 2)
        self._wait_until(lambda: self.window.selected_file_paths() == [remaining])
        self._wait_until(
            lambda: [
                self.window.keywordsList.item(index).text()
                for index in range(self.window.keywordsList.count())
            ]
            == ["confirmed", "queued"]
        )

        self.assertEqual(
            [path for path, _tags in FakeExifTool.write_calls], [departed, remaining]
        )

    def test_later_tag_mutation_uses_fresh_external_metadata_after_earlier_failure(
        self,
    ) -> None:
        (path,) = self._add_paths("one.jpg")
        self._wait_until(lambda: self.window.keywordsList.count() == 1)
        FakeExifTool.block_writes()
        FakeExifTool.write_failures = [True, False]

        self.window.addEdit.setText("first")
        self.window.add_keyword_from_input()
        self._wait_until(lambda: len(FakeExifTool.write_calls) == 1)

        self.window.addEdit.setText("second")
        self.window.add_keyword_from_input()
        FakeExifTool.states_by_path[path] = KeywordState(
            ["confirmed", "external"], ["confirmed", "external"]
        )

        with patch("exif_ui.QtWidgets.QMessageBox.critical"):
            FakeExifTool.release_writes()
            self._wait_until(lambda: len(FakeExifTool.write_calls) == 2)
            self._wait_until(
                lambda: "attention" in self.window.mutationStatusLabel.text()
            )

        self.assertEqual(
            FakeExifTool.write_calls[1],
            (path, ["confirmed", "external", "second"]),
        )
        self.assertEqual(
            [
                self.window.keywordsList.item(index).text()
                for index in range(self.window.keywordsList.count())
            ],
            ["confirmed", "external", "second"],
        )

    def test_focus_current_tags_command_is_listed_with_its_shortcut(self) -> None:
        action = self.window._actions_by_id["focuskeywords"]

        self.assertEqual(action.command.name, "focuscurrenttags")
        self.assertEqual(action.shortcuts[0].sequence, "Alt+3")

    def test_search_controls_explain_their_keyboard_shortcuts(self) -> None:
        self.assertIn("Ctrl+Shift+F", self.window.dbSearchEdit.toolTip())
        self.assertIn("Ctrl+Shift+X", self.window.dbSearchClearBtn.toolTip())

    def test_search_command_accepts_tab_and_preserves_internal_whitespace(self) -> None:
        self._add_paths("one.jpg")
        self.window.cmdLine.setText(":search\ttag:two\t  words")

        self.window._execute_command_line()
        self.discovery_runner.run_index_work()

        self.assertEqual(FakePhotoIndex.search_queries, ["tag:two\t  words"])

    def test_search_actions_are_catalogue_backed(self) -> None:
        search = self.window._actions_by_id["search"]
        clear = self.window._actions_by_id["clearsearch"]

        self.assertEqual(search.command.name, "search")
        self.assertTrue(search.command.accepts_arguments)
        self.assertEqual(clear.command.name, "clearsearch")
        self.assertEqual(clear.command.aliases, ("clear", "back"))
        self.assertEqual(clear.shortcuts[0].sequence, "Ctrl+Shift+X")

    def test_reindex_command_refreshes_the_active_root_with_non_modal_feedback(
        self,
    ) -> None:
        self._add_paths("one.jpg")
        FakePhotoIndex.refresh_stale = True

        self.window._dispatch_command("reindex", [])

        self.assertEqual(self.window.statusBar().currentMessage(), "Reindexing photos…")
        self.discovery_runner.run_index_work()
        self.app.processEvents()

        self.assertEqual(FakePhotoIndex.refresh_calls, ["refresh"])
        self.assertEqual(self.window.statusBar().currentMessage(), "Reindex complete")

    def test_departed_reindex_completion_does_not_replace_current_feedback(
        self,
    ) -> None:
        self._add_paths("one.jpg")
        self.window._dispatch_command("reindex", [])
        replacement = normalize_path("C:/other/replacement.jpg")
        self.window.replace_photo_workspace([replacement])
        self.window.statusBar().showMessage("New workspace")

        self.discovery_runner.run_index_work()
        self.app.processEvents()

        self.assertEqual(self.window.statusBar().currentMessage(), "New workspace")

    def test_adding_paths_preserves_order_and_suppresses_duplicates(self) -> None:
        first, second, duplicate = self._add_paths(
            "first.jpg", "second.jpg", "first.jpg"
        )

        self.assertEqual(self.window.all_file_paths(), [first, second])
        self.assertEqual(
            [
                self.window.files.item(index).text()
                for index in range(self.window.files.count())
            ],
            [first, second],
        )
        self.assertEqual(self.window.selected_file_paths(), [first])
        self.assertEqual(
            [item.text() for item in self.window.files.selectedItems()], [first]
        )
        self.assertEqual(duplicate, first)

    def test_selecting_another_photo_updates_the_active_photo_and_label(self) -> None:
        _first, second, _duplicate = self._add_paths(
            "first.jpg", "second.jpg", "first.jpg"
        )

        self.window._move_list_selection(self.window.files, +1)
        self.app.processEvents()

        self.assertEqual(self.window.selected_file_paths(), [second])
        self.assertEqual(self.window.selectedLabel.text(), second)

    def test_file_pane_arrow_keys_change_the_active_photo(self) -> None:
        first, second, _duplicate = self._add_paths(
            "first.jpg", "second.jpg", "first.jpg"
        )
        self.window.files.setFocus()

        QtTest.QTest.keyClick(self.window.files, QtCore.Qt.Key.Key_Down)
        self.app.processEvents()
        self.assertEqual(self.window.selected_file_paths(), [second])
        self.assertEqual(self.window.selectedLabel.text(), second)

        QtTest.QTest.keyClick(self.window.files, QtCore.Qt.Key.Key_Up)
        self.app.processEvents()
        self.assertEqual(self.window.selected_file_paths(), [first])
        self.assertEqual(self.window.selectedLabel.text(), first)

    def test_file_pane_j_and_k_change_the_active_photo(self) -> None:
        first, second, _duplicate = self._add_paths(
            "first.jpg", "second.jpg", "first.jpg"
        )
        self.window.files.setFocus()

        QtTest.QTest.keyClick(self.window.files, QtCore.Qt.Key.Key_J)
        self.app.processEvents()
        self.assertEqual(self.window.selected_file_paths(), [second])
        self.assertEqual(self.window.selectedLabel.text(), second)

        QtTest.QTest.keyClick(self.window.files, QtCore.Qt.Key.Key_K)
        self.app.processEvents()
        self.assertEqual(self.window.selected_file_paths(), [first])
        self.assertEqual(self.window.selectedLabel.text(), first)

    def test_clicking_another_photo_updates_the_active_photo_and_label(self) -> None:
        _first, second, _duplicate = self._add_paths(
            "first.jpg", "second.jpg", "first.jpg"
        )
        second_rect = self.window.files.visualItemRect(self.window.files.item(1))

        QtTest.QTest.mouseClick(
            self.window.files.viewport(),
            QtCore.Qt.MouseButton.LeftButton,
            pos=second_rect.center(),
        )
        self.app.processEvents()

        self.assertEqual(self.window.selected_file_paths(), [second])
        self.assertEqual(self.window.selectedLabel.text(), second)

    def test_iptc_filter_keeps_the_source_view_and_checkbox_unchecked_while_scanning(
        self,
    ) -> None:
        first, second = self._add_paths("first.jpg", "second.jpg")
        self.window.files.setCurrentItem(
            self.window.files.item(1),
            QtCore.QItemSelectionModel.SelectionFlag.ClearAndSelect,
        )
        self.app.processEvents()

        self.window.onlyUntagged.setChecked(True)

        self.assertFalse(self.window.onlyUntagged.isChecked())
        self.assertEqual(self.window.selected_file_paths(), [second])
        self.assertEqual(
            [
                self.window.files.item(index).text()
                for index in range(self.window.files.count())
                if not self.window.files.item(index).isHidden()
            ],
            [first, second],
        )

    def test_clearing_a_completed_iptc_filter_restores_and_scrolls_to_source_selection(
        self,
    ) -> None:
        paths = self._add_paths(*(f"photo-{index}.jpg" for index in range(100)))
        target = paths[40]
        self.window.files.setCurrentItem(
            self.window.files.item(40),
            QtCore.QItemSelectionModel.SelectionFlag.ClearAndSelect,
        )
        self.app.processEvents()

        self.window.onlyUntagged.setChecked(True)
        self._wait_until(self.window.onlyUntagged.isChecked)
        self.assertEqual(self.window.selected_file_paths(), [])

        self.window.onlyUntagged.setChecked(False)
        self.app.processEvents()

        self.assertEqual(self.window.selected_file_paths(), [target])
        self.assertLessEqual(
            abs(self.window.files.visualItemRect(self.window.files.item(40)).top()), 1
        )

    def test_failed_iptc_filter_restores_and_scrolls_to_source_selection(
        self,
    ) -> None:
        paths = self._add_paths(*(f"photo-{index}.jpg" for index in range(100)))
        target = paths[40]
        self.window.files.setCurrentItem(
            self.window.files.item(40),
            QtCore.QItemSelectionModel.SelectionFlag.ClearAndSelect,
        )
        self.app.processEvents()
        FakeExifTool.scan_error = RuntimeError("simulated filter failure")

        with patch("exif_ui.QtWidgets.QMessageBox.critical") as critical:
            self.window.onlyUntagged.setChecked(True)
            self._wait_until(
                lambda: self.window.statusBar()
                .currentMessage()
                .startswith("Filtering IPTC-empty failed:")
            )

        self.assertFalse(self.window.onlyUntagged.isChecked())
        self.assertEqual(self.window.filterInfoLabel.text(), "Folder view · 100 photos")
        self.assertEqual(self.window.selected_file_paths(), [target])
        self.assertLessEqual(
            abs(self.window.files.visualItemRect(self.window.files.item(40)).top()), 1
        )
        critical.assert_not_called()

    def test_db_search_shows_external_indexed_matches_and_back_restores_folder(
        self,
    ) -> None:
        first, second, _duplicate = self._add_paths(
            "first.jpg", "second.jpg", "first.jpg"
        )
        external = normalize_path("C:/photos/indexed-only.jpg")

        FakePhotoIndex.search_results = {external}
        self.window._dispatch_command("search", ["tag:indexed-only"])
        self.assertEqual(self.window.dbSearchEdit.text(), "tag:indexed-only")
        self.discovery_runner.run_index_work()
        self.app.processEvents()

        self.assertEqual(self.window.all_file_paths(), [external])
        self.assertEqual(self.window.files.count(), 1)
        self.assertEqual(self.window.selected_file_paths(), [external])
        self._wait_until(lambda: self.window.keywordsList.count() == 1)

        self.window.addEdit.setText("indexed")
        self.window.add_keyword_from_input()
        self._wait_until(lambda: len(FakeExifTool.write_calls) == 1)
        self.assertEqual(FakeExifTool.write_calls[0][0], external)

        self.window._dispatch_command("back", [])
        self.app.processEvents()

        self.assertEqual(self.window.all_file_paths(), [first, second])
        self.assertEqual(self.window.selected_file_paths(), [first])
        self.assertEqual(self.window.dbSearchEdit.text(), "")

    def test_back_restores_the_folder_scroll_anchor(self) -> None:
        paths = self._add_paths(*(f"photo-{index}.jpg" for index in range(100)))
        target = paths[40]
        self.window.files.setCurrentItem(
            self.window.files.item(40),
            QtCore.QItemSelectionModel.SelectionFlag.ClearAndSelect,
        )
        self.window.files.scrollToItem(
            self.window.files.item(40),
            QtWidgets.QAbstractItemView.ScrollHint.PositionAtTop,
        )
        self.app.processEvents()

        FakePhotoIndex.search_results = {normalize_path("C:/photos/indexed-only.jpg")}
        self.window.dbSearchEdit.setText("tag:indexed-only")
        self.window.apply_db_search()
        self.discovery_runner.run_index_work()
        self.app.processEvents()
        self.window._dispatch_command("back", [])
        self.app.processEvents()

        self.assertEqual(self.window.selected_file_paths(), [target])
        self.assertLessEqual(
            abs(self.window.files.visualItemRect(self.window.files.item(40)).top()), 1
        )

    def test_newer_search_supersedes_an_older_background_result(self) -> None:
        first, second, _duplicate = self._add_paths(
            "first.jpg", "second.jpg", "first.jpg"
        )
        FakePhotoIndex.search_results = {first}
        self.window.dbSearchEdit.setText("tag:first")
        self.window.apply_db_search()
        FakePhotoIndex.search_results = {second}
        self.window.dbSearchEdit.setText("tag:second")
        self.window.apply_db_search()

        self.discovery_runner.run_index_work()
        self.app.processEvents()

        self.assertEqual(self.window.all_file_paths(), [second])
        self.assertEqual(self.window.files.count(), 1)
        self.assertEqual(self.window.selected_file_paths(), [second])
        self.assertEqual(
            self.window.filterInfoLabel.text(),
            "Search: tag:second · 1 results · :back",
        )

    def test_known_tag_filter_uses_the_loaded_snapshot_without_a_read(self) -> None:
        self._add_paths("one.jpg")
        FakePhotoIndex.known_tags = {"coordinator-bird", "coordinator-beach"}
        self.window.force_refresh_known_tags()
        self.discovery_runner.run_index_work()
        self.app.processEvents()
        self.assertIn(
            "coordinator-bird",
            [
                self.window.knownList.item(index).text()
                for index in range(self.window.knownList.count())
            ],
        )

        reads_before_filter = FakePhotoIndex.known_tag_reads
        self.window.knownFilter.setText("bird")
        self.app.processEvents()

        self.assertEqual(FakePhotoIndex.known_tag_reads, reads_before_filter)
        self.assertEqual(
            [
                self.window.knownList.item(index).text()
                for index in range(self.window.knownList.count())
            ],
            ["coordinator-bird"],
        )

    def test_known_tags_remain_visible_until_the_current_read_completes(self) -> None:
        self._add_paths("one.jpg")
        FakePhotoIndex.known_tags = {"first-snapshot"}
        self.window.force_refresh_known_tags()
        self.discovery_runner.run_index_work()
        self.app.processEvents()

        FakePhotoIndex.known_tags = {"second-snapshot"}
        self.window.force_refresh_known_tags()

        self.assertIn(
            "first-snapshot",
            [
                self.window.knownList.item(index).text()
                for index in range(self.window.knownList.count())
            ],
        )

        self.discovery_runner.run_index_work()
        self.app.processEvents()
        self.assertIn(
            "second-snapshot",
            [
                self.window.knownList.item(index).text()
                for index in range(self.window.knownList.count())
            ],
        )

    def test_clear_search_shortcut_restores_all_photos(self) -> None:
        _first, second, _duplicate = self._add_paths(
            "first.jpg", "second.jpg", "first.jpg"
        )

        FakePhotoIndex.search_results = {second}
        self.window.dbSearchEdit.setText("tag:second")
        self.window.apply_db_search()
        self.discovery_runner.run_index_work()
        self.app.processEvents()

        QtTest.QTest.keyClick(
            self.window,
            QtCore.Qt.Key.Key_X,
            QtCore.Qt.KeyboardModifier.ControlModifier
            | QtCore.Qt.KeyboardModifier.ShiftModifier,
        )
        self.app.processEvents()

        self.assertEqual(self.window.files.count(), 2)
        self.assertFalse(self.window.files.item(0).isHidden())
        self.assertFalse(self.window.files.item(1).isHidden())
        self.assertEqual(self.window.dbSearchEdit.text(), "")
        self.assertEqual(self.window.filterInfoLabel.text(), "Folder view · 2 photos")

    def test_escape_restores_a_completed_search_before_leaving_the_file_pane(
        self,
    ) -> None:
        first, second = self._add_paths("first.jpg", "second.jpg")
        FakePhotoIndex.search_results = {second}
        self.window.dbSearchEdit.setText("tag:second")
        self.window.apply_db_search()
        self.discovery_runner.run_index_work()
        self.app.processEvents()
        self.window.files.setFocus()

        QtTest.QTest.keyClick(self.window.files, QtCore.Qt.Key.Key_Escape)
        self.app.processEvents()

        self.assertEqual(self.window.all_file_paths(), [first, second])
        self.assertEqual(self.window.dbSearchEdit.text(), "")
        self.assertEqual(self.window.filterInfoLabel.text(), "Folder view · 2 photos")

    def test_escape_hides_tag_completion_and_exits_tag_input(self) -> None:
        self.window.knownList.addItems(["bird", "birch"])
        self.window.addEdit.setText("bi")
        self.window.addEdit.setFocus()

        QtTest.QTest.keyClick(self.window.addEdit, QtCore.Qt.Key.Key_Tab)
        tag_hint = next(
            label
            for label in self.window.findChildren(QtWidgets.QLabel)
            if label.text() == "birch, bird"
        )
        self.assertTrue(tag_hint.isVisible())

        QtTest.QTest.keyClick(self.window.addEdit, QtCore.Qt.Key.Key_Escape)
        self.app.processEvents()
        self.assertFalse(tag_hint.isVisible())
        self.assertIsNot(self.window.focusWidget(), self.window.addEdit)


class DeterministicCoordinatorRunner:
    def __init__(self) -> None:
        self.scheduled: list[Callable[[], None]] = []

    def submit(self, work: Callable[[], None]) -> None:
        self.scheduled.append(work)

    def run(self, index: int = 0) -> None:
        self.scheduled.pop(index)()

    def run_index_work(self) -> None:
        while self.scheduled and self.scheduled[0].__name__ != "work":
            self.run()

    def run_discovery(self, index: int = 0) -> None:
        discovery_indexes = [
            position
            for position, work in enumerate(self.scheduled)
            if work.__name__ == "work"
        ]
        self.run(discovery_indexes[index])


class FakePhotoDiscovery:
    def __init__(self) -> None:
        self.results: dict[str, list[str] | Exception] = {}

    def discover(self, root: str) -> list[str]:
        result = self.results[root]
        if isinstance(result, Exception):
            raise result
        return result


class FakeExifTool:
    fail_writes = False
    scan_error: Exception | None = None
    write_failures: list[bool] = []
    write_calls: list[tuple[str, list[str]]] = []
    states_by_path: dict[str, KeywordState] = {}
    write_started = threading.Event()
    _allow_writes = threading.Event()

    @classmethod
    def reset(cls) -> None:
        cls.fail_writes = False
        cls.scan_error = None
        cls.write_failures = []
        cls.write_calls = []
        cls.states_by_path = {}
        cls.write_started = threading.Event()
        cls._allow_writes = threading.Event()
        cls._allow_writes.set()

    @classmethod
    def block_writes(cls) -> None:
        cls._allow_writes.clear()

    @classmethod
    def release_writes(cls) -> None:
        cls._allow_writes.set()

    def read_keywords(self, path: str) -> "KeywordState":
        return type(self).states_by_path.get(
            normalize_path(path), KeywordState(["confirmed"], ["confirmed"])
        )

    def read_keywords_many(self, paths: list[str]) -> dict[str, "KeywordState"]:
        return {normalize_path(path): self.read_keywords(path) for path in paths}

    def scan_iptc_empty(self, paths: list[str]) -> set[str]:
        del paths
        if type(self).scan_error is not None:
            raise type(self).scan_error
        return set()

    def write_keywords(
        self, paths: list[str], keywords: list[str], keep_backup: bool
    ) -> None:
        del keep_backup
        path = normalize_path(paths[0])
        type(self).write_calls.append((path, list(keywords)))
        type(self).write_started.set()
        type(self)._allow_writes.wait(timeout=2)
        failed = type(self).fail_writes or (
            type(self).write_failures.pop(0) if type(self).write_failures else False
        )
        if failed:
            raise RuntimeError("simulated write failure")
        type(self).states_by_path[path] = KeywordState(list(keywords), list(keywords))


class FakePhotoIndex:
    search_results: set[str] = set()
    search_queries: list[str] = []
    refresh_stale = False
    refresh_calls: list[str] = []
    states_by_path: dict[str, KeywordState] = {}
    known_tags: set[str] = set()
    known_tag_reads = 0

    @classmethod
    def reset(cls) -> None:
        cls.search_results = set()
        cls.search_queries = []
        cls.refresh_stale = False
        cls.refresh_calls = []
        cls.states_by_path = {}
        cls.known_tags = set()
        cls.known_tag_reads = 0

    def __init__(self, _root: str) -> None:
        pass

    def is_initialized(self) -> bool:
        return True

    def is_refresh_stale(self) -> bool:
        return type(self).refresh_stale

    def sync_root(self, _exif) -> object:
        type(self).refresh_calls.append("refresh")
        type(self).refresh_stale = False
        return object()

    def load_tags_for_root(self) -> set[str]:
        type(self).known_tag_reads += 1
        return type(self).known_tags

    def update_states(self, states: dict[str, "KeywordState"]) -> None:
        type(self).states_by_path.update(states)

    def has_photos(self, paths: list[str]) -> set[str]:
        return {normalize_path(path) for path in paths}

    def sync_paths(self, _exif, _paths: list[str]) -> object:
        return object()

    def index_missing(self, _root: str, _paths: list[str]) -> int:
        return 0

    def search_photos(self, query: str) -> set[str]:
        type(self).search_queries.append(query)
        return self.search_results


if __name__ == "__main__":
    unittest.main()
