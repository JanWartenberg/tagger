"""Windows/offscreen characterization tests for the current Qt adapter.

These tests deliberately exercise public MainWindow entrypoints and widgets.  They
are a behavior baseline for the Photo Workspace refactor, not tests of private
state or rendering details.
"""

from __future__ import annotations

import os
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


@unittest.skipUnless(PYQT_AVAILABLE, "PyQt6 is required for Qt adapter characterization tests")
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
        self.window = MainWindow()
        self.window.show()
        self.window.activateWindow()
        self.app.processEvents()
        self.addCleanup(self.window.close)

    def _add_paths(self, *names: str) -> list[str]:
        paths = [str(Path("C:/photos") / name) for name in names]
        self.window.add_files(paths)
        self.app.processEvents()
        return [normalize_path(path) for path in paths]

    def test_adding_paths_preserves_order_and_suppresses_duplicates(self) -> None:
        first, second, duplicate = self._add_paths("first.jpg", "second.jpg", "first.jpg")

        self.assertEqual(self.window.all_file_paths(), [first, second])
        self.assertEqual(
            [self.window.files.item(index).text() for index in range(self.window.files.count())],
            [first, second],
        )
        self.assertEqual(self.window.selected_file_paths(), [first])
        self.assertEqual([item.text() for item in self.window.files.selectedItems()], [first])
        self.assertEqual(duplicate, first)

    def test_selecting_another_photo_updates_the_active_photo_and_label(self) -> None:
        _first, second, _duplicate = self._add_paths("first.jpg", "second.jpg", "first.jpg")

        self.window.files.setCurrentRow(1)
        self.app.processEvents()

        self.assertEqual(self.window.selected_file_paths(), [second])
        self.assertEqual(self.window.selectedLabel.text(), second)

    def test_db_search_hides_non_matches_and_selects_first_visible_photo(self) -> None:
        first, second, _duplicate = self._add_paths("first.jpg", "second.jpg", "first.jpg")

        FakePhotoIndex.search_results = {second}
        self.window.dbSearchEdit.setText("tag:second")
        self.window.apply_db_search()
        self.app.processEvents()

        self.assertTrue(self.window.files.item(0).isHidden())
        self.assertFalse(self.window.files.item(1).isHidden())
        self.assertEqual(self.window.selected_file_paths(), [second])

        self.window.clear_db_search()
        self.app.processEvents()
        self.assertFalse(self.window.files.item(0).isHidden())
        self.assertFalse(self.window.files.item(1).isHidden())
        self.assertIn(self.window.selected_file_paths()[0], {first, second})

    def test_escape_hides_tag_completion_and_exits_tag_input(self) -> None:
        self.window.knownList.addItems(["bird", "birch"])
        self.window.addEdit.setText("bi")
        self.window.addEdit.setFocus()

        QtTest.QTest.keyClick(self.window.addEdit, QtCore.Qt.Key.Key_Tab)
        tag_hint = next(
            label
            for label in self.window.findChildren(QtWidgets.QLabel)
            if label.text() == "bird, birch"
        )
        self.assertTrue(tag_hint.isVisible())

        QtTest.QTest.keyClick(self.window.addEdit, QtCore.Qt.Key.Key_Escape)
        self.app.processEvents()
        self.assertFalse(tag_hint.isVisible())
        self.assertIsNot(self.window.focusWidget(), self.window.addEdit)


class FakeExifTool:
    def read_keywords(self, _path: str) -> "KeywordState":
        return KeywordState([], [])

    def read_keywords_many(self, paths: list[str]) -> dict[str, "KeywordState"]:
        return {normalize_path(path): KeywordState([], []) for path in paths}

    def write_keywords(self, _paths: list[str], _keywords: list[str], keep_backup: bool) -> None:
        del keep_backup


class FakePhotoIndex:
    search_results: set[str] = set()

    def __init__(self, _root: str) -> None:
        pass

    def is_initialized(self) -> bool:
        return True

    def load_tags_for_root(self) -> set[str]:
        return set()

    def search_photos(self, _query: str) -> set[str]:
        return self.search_results


if __name__ == "__main__":
    unittest.main()
