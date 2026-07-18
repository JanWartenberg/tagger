"""Windows/offscreen characterization tests for the current Qt adapter.

These tests deliberately exercise public MainWindow entrypoints and widgets.  They
are a behavior baseline for the Photo Workspace refactor, not tests of private
state or rendering details.
"""

from __future__ import annotations

import os
import threading
import time
import unittest
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
        self.window = MainWindow()
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
        self.app.processEvents()
        return [normalize_path(path) for path in paths]

    def _wait_until(self, condition) -> None:
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            self.app.processEvents()
            if condition():
                return
            QtTest.QTest.qWait(10)
        self.fail("Timed out waiting for asynchronous UI work")

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
            self._wait_until(lambda: "Failed" in self.window.mutationStatusLabel.text())

        self.assertFalse(item.icon().isNull())
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
            self._wait_until(lambda: "Failed" in self.window.mutationStatusLabel.text())

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

    def test_clear_search_action_has_command_alias_and_shortcut(self) -> None:
        action = self.window._actions_by_id["clearsearch"]

        self.assertEqual(action.command.name, "clearsearch")
        self.assertEqual(action.command.aliases, ("clear",))
        self.assertEqual(action.shortcuts[0].sequence, "Ctrl+Shift+X")

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

    def test_db_search_hides_non_matches_and_selects_first_visible_photo(self) -> None:
        first, second, _duplicate = self._add_paths(
            "first.jpg", "second.jpg", "first.jpg"
        )

        FakePhotoIndex.search_results = {second}
        self.window.dbSearchEdit.setText("tag:second")
        self.window.apply_db_search()
        self.app.processEvents()

        self.assertTrue(self.window.files.item(0).isHidden())
        self.assertFalse(self.window.files.item(1).isHidden())
        self.assertEqual(self.window.selected_file_paths(), [second])

        self.window._dispatch_command("clear", [])
        self.app.processEvents()
        self.assertFalse(self.window.files.item(0).isHidden())
        self.assertFalse(self.window.files.item(1).isHidden())
        self.assertIn(self.window.selected_file_paths()[0], {first, second})

    def test_clear_search_shortcut_restores_all_photos(self) -> None:
        _first, second, _duplicate = self._add_paths(
            "first.jpg", "second.jpg", "first.jpg"
        )

        FakePhotoIndex.search_results = {second}
        self.window.dbSearchEdit.setText("tag:second")
        self.window.apply_db_search()
        self.app.processEvents()

        QtTest.QTest.keyClick(
            self.window,
            QtCore.Qt.Key.Key_X,
            QtCore.Qt.KeyboardModifier.ControlModifier
            | QtCore.Qt.KeyboardModifier.ShiftModifier,
        )
        self.app.processEvents()

        self.assertFalse(self.window.files.item(0).isHidden())
        self.assertFalse(self.window.files.item(1).isHidden())
        self.assertEqual(self.window.dbSearchEdit.text(), "")

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


class FakeExifTool:
    fail_writes = False
    write_failures: list[bool] = []
    write_calls: list[tuple[str, list[str]]] = []
    states_by_path: dict[str, KeywordState] = {}
    write_started = threading.Event()
    _allow_writes = threading.Event()

    @classmethod
    def reset(cls) -> None:
        cls.fail_writes = False
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
    states_by_path: dict[str, KeywordState] = {}

    @classmethod
    def reset(cls) -> None:
        cls.search_results = set()
        cls.states_by_path = {}

    def __init__(self, _root: str) -> None:
        pass

    def is_initialized(self) -> bool:
        return True

    def load_tags_for_root(self) -> set[str]:
        return set()

    def update_states(self, states: dict[str, "KeywordState"]) -> None:
        type(self).states_by_path.update(states)

    def has_photos(self, paths: list[str]) -> set[str]:
        return {normalize_path(path) for path in paths}

    def search_photos(self, _query: str) -> set[str]:
        return self.search_results


if __name__ == "__main__":
    unittest.main()
