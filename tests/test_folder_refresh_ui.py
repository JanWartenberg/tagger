"""Refresh-folder behavior through public Qt entrypoints with boundary adapters."""

from pathlib import Path
from unittest.mock import patch

import pytest
from PyQt6 import QtCore, QtTest, QtWidgets

import test_main_window_characterization as ui
from tagger_app.utils import normalize_path


@pytest.fixture
def harness(monkeypatch):
    ui.MainWindowCharacterizationTests.setUpClass()
    case = ui.MainWindowCharacterizationTests("runTest")
    case.setUp()
    monkeypatch.setattr(
        "tagger_app.ui.main_window.resolve_index_root",
        lambda *args, **kwargs: Path(normalize_path("C:/photos")),
    )
    refreshed = {}
    monkeypatch.setattr(
        case.discovery, "discover_refresh", case.discovery.discover, raising=False
    )

    def refresh_folder(self, exif, folder):
        result = refreshed[normalize_path(folder)]
        if isinstance(result, Exception):
            raise result
        return tuple(map(normalize_path, result))

    monkeypatch.setattr(
        ui.FakePhotoIndex, "refresh_folder", refresh_folder, raising=False
    )
    try:
        yield case, refreshed
    finally:
        case.doCleanups()


def load(case, folder, paths):
    case.discovery.results[folder] = paths
    case._choose_folder(folder)
    case.discovery_runner.run_discovery()
    case._wait_until(lambda: case.window.files.count() == len(paths))


def refresh_key(case):
    case.window.activateWindow()
    case.app.processEvents()
    case.window.files.setFocus()
    QtTest.QTest.keyClick(case.window.files, QtCore.Qt.Key.Key_F5)
    case.app.processEvents()


def test_f5_inserts_new_direct_photo_above_subfolders(harness):
    case, refreshed = harness
    folder = normalize_path("C:/photos/birds")
    direct, nested, added = [
        str(Path(folder) / name)
        for name in ("Zebra.JPG", "a/nested.jpg", "Meerstrand.JPG")
    ]
    load(case, folder, [nested, direct])
    assert case.window.all_file_paths() == [direct, nested]
    case.window.files.setCurrentRow(1)
    refreshed[folder] = [nested, direct, added]
    refresh_key(case)
    case._wait_until(lambda: added in case.window.all_file_paths())
    assert case.window.all_file_paths() == [added, direct, nested]
    assert case.window.active_file_path() == nested


def test_grouped_folder_order_survives_filter_composition_and_search_return(harness):
    case, _ = harness

    def visible():
        view = case.window.files
        return [
            view.item(i).text()
            for i in range(view.count())
            if not view.item(i).isHidden()
        ]

    folder = normalize_path("C:/photos/birds")
    direct, nested, excluded = [
        str(Path(folder) / name)
        for name in ("Zebra-match.JPG", "a/match.jpg", "hidden/match.jpg")
    ]
    load(case, folder, [excluded, nested, direct])
    expected = [direct, nested, excluded]
    assert case.window.all_file_paths() == expected
    case.window.filenameFilterEdit.setText("match")
    QtTest.QTest.keyClick(case.window.filenameFilterEdit, QtCore.Qt.Key.Key_Return)
    ui.FakePhotoIndex.iptc_empty_results = {direct, nested, excluded}
    case.window.onlyUntagged.setChecked(True)
    case._wait_until(
        lambda: case.window.statusBar().currentMessage() == "IPTC-empty results ready"
    )
    case.window.directoryExcludeEdit.setText("hidden")
    QtTest.QTest.keyClick(case.window.directoryExcludeEdit, QtCore.Qt.Key.Key_Return)
    assert visible() == [direct, nested]
    case.window.clear_all_filters()
    assert visible() == expected
    ui.FakePhotoIndex.search_results = {direct, nested}
    case.window.dbDateSearchEdit.setText("2026-10")
    case.window.apply_db_search()
    case._wait_until(
        lambda: case.window.statusBar().currentMessage().startswith("DB search:")
    )
    assert set(visible()) == {direct, nested}
    case.window.clear_db_search()
    assert case.window.all_file_paths() == expected
    assert visible() == expected


def test_dropped_folders_keep_drop_order_and_group_direct_photos_per_folder(
    harness, tmp_path
):
    case, _ = harness
    first, second = tmp_path / "z-first", tmp_path / "a-second"
    first.mkdir()
    second.mkdir()
    first_direct, first_nested = str(first / "Zebra.JPG"), str(first / "a/nested.jpg")
    second_direct, second_nested = (
        str(second / "Zebra.JPG"),
        str(second / "a/nested.jpg"),
    )
    case.discovery.results[str(first)] = [first_nested, first_direct]
    case.discovery.results[str(second)] = [second_nested, second_direct]
    case.window.handle_dropped_urls(
        [QtCore.QUrl.fromLocalFile(str(first)), QtCore.QUrl.fromLocalFile(str(second))]
    )
    case.discovery_runner.run_discovery(1)
    assert case.window.all_file_paths() == []
    case.discovery_runner.run_discovery()
    case._wait_until(lambda: case.window.files.count() == 4)
    assert case.window.all_file_paths() == [
        first_direct,
        first_nested,
        second_direct,
        second_nested,
    ]


@pytest.mark.parametrize("count", [120, 510])
def test_grouped_refresh_preserves_filtered_partial_scroll_anchor(harness, count):
    case, refreshed = harness
    folder = normalize_path("C:/photos/birds")
    direct = str(Path(folder) / "Zebra-match.JPG")
    nested = [str(Path(folder) / f"a/match-{i:04}.jpg") for i in range(count)]
    hidden = str(Path(folder) / "hidden.jpg")
    load(case, folder, nested + [hidden, direct])
    case.window.filenameFilterEdit.setText("match")
    QtTest.QTest.keyClick(case.window.filenameFilterEdit, QtCore.Qt.Key.Key_Return)
    QtTest.QTest.qWait(QtWidgets.QApplication.doubleClickInterval() + 100)
    view = case.window.files
    view.setCurrentRow(61)
    view.scrollToItem(
        view.item(60), QtWidgets.QAbstractItemView.ScrollHint.PositionAtTop
    )
    case.app.processEvents()
    view.verticalScrollBar().setValue(view.verticalScrollBar().value() + 7)
    anchor_path = view.item(60).text()
    offset = view.visualItemRect(view.item(60)).top()
    assert offset == -7
    selection = case.window.selected_file_paths()
    added = str(Path(folder) / "Meerstrand-match.JPG")
    refreshed[folder] = nested + [hidden, direct, added]
    refresh_key(case)
    case._wait_until(lambda: view.count() == count + 3 and view.isEnabled(), timeout=10)
    QtTest.QTest.qWait(QtWidgets.QApplication.doubleClickInterval() + 100)
    assert case.window.all_file_paths()[:3] == [hidden, added, direct]
    anchor = next(
        view.item(i) for i in range(view.count()) if view.item(i).text() == anchor_path
    )
    assert view.visualItemRect(anchor).top() == offset
    assert case.window.selected_file_paths() == selection
    assert view.item(0).isHidden()


def test_f5_refresh_keeps_view_until_complete_and_preserves_filters_selection(harness):
    case, refreshed = harness
    folder = normalize_path("C:/photos/birds")
    first, gone, added = [
        str(Path(folder) / n) for n in ("keep.jpg", "gone.jpg", "keep-new.jpg")
    ]
    load(case, folder, [first, gone])
    case.window.filenameFilterEdit.setText("keep")
    case.window.apply_filename_filter()
    refreshed[folder] = [first, added]
    refresh_key(case)
    assert set(case.window.all_file_paths()) == {first, gone}
    case._wait_until(lambda: added in case.window.all_file_paths())
    assert set(case.window.all_file_paths()) == {first, added}
    assert case.window.selected_file_paths() == [first]
    assert case.window.filenameFilterEdit.text() == "keep"
    assert ui.FakePhotoIndex.refresh_calls == []


def test_refresh_reapplies_current_date_search(harness):
    case, refreshed = harness
    folder = normalize_path("C:/photos/birds")
    first, added = [str(Path(folder) / n) for n in ("first.jpg", "new.jpg")]
    load(case, folder, [first])
    ui.FakePhotoIndex.search_results = {first}
    case.window.dbDateSearchEdit.setText("2026-10")
    case.window.apply_db_search()
    case._wait_until(
        lambda: case.window.statusBar().currentMessage().startswith("DB search:")
    )
    refreshed[folder] = [first, added]
    ui.FakePhotoIndex.search_results = {first, added}
    refresh_key(case)
    case._wait_until(lambda: added in case.window.all_file_paths())
    assert ui.FakePhotoIndex.search_queries == ["date:2026-10", "date:2026-10"]
    assert ui.FakePhotoIndex.refresh_calls == []


def test_unknown_refresh_target_picker_cancellation_is_noop(harness):
    case, _ = harness
    with patch(
        "tagger_app.ui.main_window.QtWidgets.QFileDialog.getExistingDirectory",
        return_value="",
    ) as picker:
        refresh_key(case)
    picker.assert_called_once()
    assert case.window.all_file_paths() == []


def test_failed_refresh_keeps_current_view(harness):
    case, refreshed = harness
    folder = normalize_path("C:/photos/birds")
    first = str(Path(folder) / "first.jpg")
    load(case, folder, [first])
    refreshed[folder] = PermissionError("unreadable folder")
    refresh_key(case)
    case._wait_until(
        lambda: "refresh failed" in case.window.statusBar().currentMessage().lower()
    )
    assert case.window.all_file_paths() == [first]


def test_refresh_completion_does_not_replace_newer_folder(harness):
    case, refreshed = harness
    folder = normalize_path("C:/photos/birds")
    first = str(Path(folder) / "first.jpg")
    load(case, folder, [first])
    refreshed[folder] = [str(Path(folder) / "new.jpg")]
    refresh_key(case)
    other = normalize_path("C:/photos/other")
    second = str(Path(other) / "second.jpg")
    case.discovery.results[other] = [second]
    case._choose_folder(other)
    case.discovery_runner.run_index_work()
    case.discovery_runner.run_discovery()
    case._wait_until(lambda: case.window.all_file_paths() == [second])
    assert case.window.all_file_paths() == [second]


def test_out_of_root_refresh_never_indexes_new_workspace_photos(harness):
    case, _ = harness
    outside = normalize_path("D:/outside")
    photo = str(Path(outside) / "photo.jpg")
    case.discovery.results[outside] = [photo]
    with patch(
        "tagger_app.ui.main_window.QtWidgets.QFileDialog.getExistingDirectory",
        return_value=outside,
    ):
        refresh_key(case)
    case._wait_until(lambda: photo in case.window.all_file_paths())
    # Let the real metadata worker and debounce finish as well as index work.
    case._wait_until(lambda: case.window.dateLabel.text().startswith("Capture date:"))
    case.discovery_runner.run_index_work()
    case.app.processEvents()
    assert "index not updated" in case.window.indexRepairStatusLabel.text()
    assert photo not in ui.FakePhotoIndex.states_by_path


def test_refresh_preserves_multiple_selection_and_active_photo(harness):
    case, refreshed = harness
    folder = normalize_path("C:/photos/birds")
    paths = [str(Path(folder) / name) for name in ("a.jpg", "b.jpg")]
    load(case, folder, paths)
    case.window.files.selectAll()
    before = case.window.selected_file_paths()
    active = case.window.active_file_path()
    refreshed[folder] = paths + [str(Path(folder) / "new.jpg")]
    refresh_key(case)
    case._wait_until(lambda: len(case.window.all_file_paths()) == 3)
    assert case.window.selected_file_paths() == before
    assert case.window.active_file_path() == active


def test_search_with_stable_iptc_filter_offers_newly_matching_photos(harness):
    case, refreshed = harness
    folder = normalize_path("C:/photos/birds")
    first, added = [str(Path(folder) / n) for n in ("first.jpg", "new.jpg")]
    load(case, folder, [first])
    ui.FakePhotoIndex.search_results = {first}
    ui.FakePhotoIndex.iptc_empty_results = {first}
    case.window.dbDateSearchEdit.setText("2026-10")
    case.window.apply_db_search()
    case._wait_until(
        lambda: case.window.statusBar().currentMessage().startswith("DB search:")
    )
    case.window.onlyUntagged.setChecked(True)
    case._wait_until(
        lambda: case.window.statusBar().currentMessage() == "IPTC-empty results ready"
    )
    refreshed[folder] = [first, added]
    ui.FakePhotoIndex.search_results = {first, added}
    ui.FakePhotoIndex.iptc_empty_results = {first, added}
    refresh_key(case)
    case._wait_until(lambda: added in case.window.all_file_paths())

    def added_item():
        return next(
            case.window.files.item(i)
            for i in range(case.window.files.count())
            if case.window.files.item(i).text() == added
        )

    assert added_item().isHidden()
    case._wait_until(lambda: case.window.iptcEmptyRefreshOffer.isVisible())
    case.window.refresh_iptc_empty_view()
    case._wait_until(lambda: not added_item().isHidden())


def test_large_refresh_preserves_multiple_selection(harness):
    case, refreshed = harness
    folder = normalize_path("C:/photos/birds")
    paths = [str(Path(folder) / f"photo-{i:04}.jpg") for i in range(501)]
    load(case, folder, paths)
    QtTest.QTest.mouseClick(
        case.window.files.viewport(),
        QtCore.Qt.MouseButton.LeftButton,
        QtCore.Qt.KeyboardModifier.ControlModifier,
        pos=case.window.files.visualItemRect(case.window.files.item(1)).center(),
    )
    before = case.window.selected_file_paths()
    assert len(before) == 2
    added = str(Path(folder) / "new.jpg")
    refreshed[folder] = paths + [added]
    refresh_key(case)
    case._wait_until(
        lambda: case.window.files.count() == 502 and case.window.files.isEnabled()
    )
    assert case.window.selected_file_paths() == before


def test_second_refresh_after_query_change_uses_current_generation(harness):
    case, refreshed = harness
    folder = normalize_path("C:/photos/birds")
    first, added = [str(Path(folder) / n) for n in ("first.jpg", "new.jpg")]
    load(case, folder, [first])
    refreshed[folder] = [first, added]
    refresh_key(case)
    ui.FakePhotoIndex.search_results = {first}
    case.window.dbDateSearchEdit.setText("2026-10")
    case.window.apply_db_search()
    # Complete the independent search before the pending folder-refresh write.
    read_position = next(
        i
        for i, work in enumerate(case.discovery_runner.scheduled)
        if work.__name__ == "read"
    )
    case.discovery_runner.run(read_position)
    case.app.processEvents()
    ui.FakePhotoIndex.search_results = {first, added}
    refresh_key(case)
    case._wait_until(lambda: added in case.window.all_file_paths())
    assert ui.FakePhotoIndex.search_queries == ["date:2026-10", "date:2026-10"]


def test_refresh_resubmits_pending_iptc_filter_for_new_membership(harness):
    case, refreshed = harness
    folder = normalize_path("C:/photos/birds")
    first, added = [str(Path(folder) / n) for n in ("first.jpg", "new.jpg")]
    load(case, folder, [first])
    ui.FakePhotoIndex.iptc_empty_results = {first, added}
    case.window.onlyUntagged.setChecked(True)
    refreshed[folder] = [first, added]
    refresh_key(case)
    # The index write may finish before the independently scheduled filter read.
    write_position = next(
        i
        for i, work in enumerate(case.discovery_runner.scheduled)
        if work.__name__ == "<lambda>"
    )
    case.discovery_runner.run(write_position)
    case.app.processEvents()
    case._wait_until(
        lambda: case.window.photo_workspace.snapshot().filter_operation_id is None
    )
    assert set(case.window.all_file_paths()) == {first, added}
    assert not any(
        case.window.files.item(i).isHidden() for i in range(case.window.files.count())
    )


def test_refresh_does_not_strand_filter_waiting_for_full_index(harness):
    case, refreshed = harness
    folder = normalize_path("C:/photos/birds")
    first = str(Path(folder) / "first.jpg")
    ui.FakePhotoIndex.refresh_stale = True
    case.discovery.results[folder] = [first]
    case._choose_folder(folder)
    case.discovery_runner.run_discovery()
    case._wait_for_ui(lambda: case.window.files.count() == 1)
    ui.FakePhotoIndex.iptc_empty_results = {first}
    case.window.onlyUntagged.setChecked(True)
    refreshed[folder] = [first]
    refresh_key(case)
    case._wait_until(
        lambda: case.window.photo_workspace.snapshot().filter_operation_id is None
    )
    assert case.window.onlyUntagged.isChecked()


def test_refresh_does_not_strand_filter_after_dependent_full_index_failure(harness):
    case, refreshed = harness
    folder = normalize_path("C:/photos/birds")
    first = str(Path(folder) / "first.jpg")
    ui.FakePhotoIndex.refresh_stale = True
    ui.FakePhotoIndex.refresh_error = RuntimeError("full index unavailable")
    case.discovery.results[folder] = [first]
    case._choose_folder(folder)
    case.discovery_runner.run_discovery()
    case._wait_for_ui(lambda: case.window.files.count() == 1)
    case.window.onlyUntagged.setChecked(True)
    refreshed[folder] = [first]
    refresh_key(case)
    case._wait_until(
        lambda: case.window.photo_workspace.snapshot().filter_operation_id is None
    )
    assert not case.window.onlyUntagged.isChecked()
    assert "failed" in case.window.indexRepairStatusLabel.text().lower()
    assert case.window.all_file_paths() == [first]
