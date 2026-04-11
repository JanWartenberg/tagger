import sys
from pathlib import Path

from PyQt6 import QtCore, QtGui, QtWidgets

from commands import Command
from exif_tool import ExifTool, ExifToolError, KeywordState
from services.tag_mutation import TagMutationResult, TagMutationService
from storage import add_recent_tag, load_config, load_recent_tags, save_config
from utils import SUPPORTED_EXTS, dedupe_casefold, extract_image_paths_from_urls, normalize_path


class FileListWidget(QtWidgets.QListWidget):
    filesDropped = QtCore.pyqtSignal(list)

    def __init__(self) -> None:
        super().__init__()
        self.setAcceptDrops(True)
        self.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection)

    def dragEnterEvent(self, event: QtGui.QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event: QtGui.QDragMoveEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event: QtGui.QDropEvent) -> None:
        paths = extract_image_paths_from_urls(event.mimeData().urls())
        if paths:
            self.filesDropped.emit(paths)
            event.acceptProposedAction()
        else:
            super().dropEvent(event)


class WorkerSignals(QtCore.QObject):
    finished = QtCore.pyqtSignal(object)
    error = QtCore.pyqtSignal(str)


class Worker(QtCore.QRunnable):
    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()

    def run(self) -> None:
        try:
            res = self.fn(*self.args, **self.kwargs)
        except Exception as e:
            self.signals.error.emit(str(e))
            return
        self.signals.finished.emit(res)


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Exif UI")
        self.setAcceptDrops(True)

        self.exif = ExifTool()
        self.tag_mutations = TagMutationService(self.exif)
        self.pool = QtCore.QThreadPool.globalInstance()
        self._keywords_cache: dict[str, KeywordState] = {}
        self._folder_tag_cache: dict[tuple[str, bool], set[str]] = {}
        self._folder_scans_inflight: set[tuple[str, bool]] = set()
        self._selection_token = 0
        self._filter_token = 0
        self._filter_queue: list[list[str]] = []
        self._filter_map: dict[str, QtWidgets.QListWidgetItem] = {}
        self._filter_shown = 0
        self._filter_total = 0
        self._filter_processed = 0
        self._filter_first_chunk = True
        self._filter_switched = False
        self._filter_preserved: set[str] = set()

        self._config = load_config()

        self.files = FileListWidget()
        self.files.filesDropped.connect(self.add_files)
        self.files.itemSelectionChanged.connect(self.on_selection_changed)
        self.files.setToolTip("Focus: f / Ctrl+W H · Navigate: j/k, gg/G")

        self.selectedLabel = QtWidgets.QLabel("Drop JPG/JPEG files here")
        self.selectedLabel.setTextInteractionFlags(QtCore.Qt.TextInteractionFlag.TextSelectableByMouse)

        self.dateLabel = QtWidgets.QLabel("")
        self.dateLabel.setTextInteractionFlags(QtCore.Qt.TextInteractionFlag.TextSelectableByMouse)
        self.copyDateBtn = QtWidgets.QPushButton("Copy EXIF date → XMP")
        self.copyDateBtn.setToolTip("Copy EXIF DateTimeOriginal to XMP:CreateDate")
        self.copyDateBtn.clicked.connect(self.copy_exif_date_to_xmp)

        self.previewLabel = QtWidgets.QLabel("No preview")
        self.previewLabel.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.previewLabel.setMinimumHeight(220)
        self.previewLabel.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Expanding
        )
        self.previewLabel.setContentsMargins(8, 8, 8, 8)
        self.previewLabel.setStyleSheet(
            "QLabel { background: palette(window); color: palette(text); "
            "border: 1px solid palette(mid); border-radius: 8px; }"
        )
        self._preview_token = 0
        self._preview_image: QtGui.QImage | None = None
        self.mismatchLabel = QtWidgets.QLabel("")
        self.mismatchLabel.setStyleSheet("color: #b45309;")
        self.resolveBtn = QtWidgets.QPushButton("Resolve (sync both)")
        self.resolveBtn.setEnabled(False)
        self.resolveBtn.clicked.connect(self.resolve_mismatch)
        self.resolveBtn.setToolTip("Resolve IPTC/XMP mismatch (Ctrl+R)")
        self.resolveBtn.setShortcut(QtGui.QKeySequence("Ctrl+R"))

        self.keywordsList = QtWidgets.QListWidget()
        self.keywordsList.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.keywordsList.setToolTip("Focus: l / Ctrl+W L · Insert: i · Yank: Ctrl+C · Paste: Ctrl+V")

        self.addEdit = QtWidgets.QLineEdit()
        self.addEdit.setPlaceholderText("Add keyword...")
        self.addEdit.returnPressed.connect(self.add_keyword_from_input)
        self.addEdit.setToolTip("Insert: i · Add: Ctrl+Enter")
        self.addBtn = QtWidgets.QPushButton("Add")
        self.addBtn.clicked.connect(self.add_keyword_from_input)
        self.addBtn.setToolTip("Add keyword to selected file(s) (Ctrl+Enter)")
        self.removeBtn = QtWidgets.QPushButton("Remove selected")
        self.removeBtn.clicked.connect(self.remove_selected_keywords)
        self.removeBtn.setToolTip("Remove selected tags from image (Del/Backspace)")
        self.removeBtn.setShortcut(QtGui.QKeySequence("Del"))

        self.keepBackup = QtWidgets.QCheckBox("Keep *_original backups (exiftool default)")
        self.keepBackup.setChecked(True)
        self.keepBackup.setToolTip("If enabled, exiftool keeps *_original backups (Ctrl+Shift+B)")

        self.knownFilter = QtWidgets.QLineEdit()
        self.knownFilter.setPlaceholderText("Filter known tags...")
        self.knownFilter.textChanged.connect(self.refresh_known_tags)
        self.knownFilter.returnPressed.connect(self._focus_first_known_tag)
        self.knownFilter.setToolTip("Focus: / or Ctrl+F")
        self.knownRefreshBtn = QtWidgets.QPushButton("Refresh")
        self.knownRefreshBtn.setFixedWidth(80)
        self.knownRefreshBtn.clicked.connect(self.force_refresh_known_tags)
        self.knownRefreshBtn.setToolTip("Refresh tag repo (F5)")
        self.knownRefreshBtn.setShortcut(QtGui.QKeySequence("F5"))
        self.knownList = QtWidgets.QListWidget()
        self.knownList.itemActivated.connect(self.add_keyword_from_known)
        self.knownList.itemDoubleClicked.connect(self.add_keyword_from_known)
        self.knownList.setToolTip("Focus: t / Ctrl+W J · Navigate: j/k, n/N")

        self.recursiveScan = QtWidgets.QCheckBox("Recursive scan")
        self.recursiveScan.setToolTip("Include subfolders when building tag repo")
        self.recursiveScan.setChecked(False)
        self.recursiveScan.toggled.connect(self.force_refresh_known_tags)

        self.onlyUntagged = QtWidgets.QCheckBox("Only IPTC-empty")
        self.onlyUntagged.setToolTip("Show only files without IPTC keywords (Ctrl+Shift+E)")
        self.onlyUntagged.toggled.connect(
            lambda _checked: self.apply_iptc_filter_async(reset_preserved=True)
        )
        self.filterInfoLabel = QtWidgets.QLabel("")
        self.filterInfoLabel.setToolTip("Filter result count")

        self.addFolderBtn = QtWidgets.QPushButton("Add folder")
        self.addFolderBtn.setToolTip("Add all JPG/JPEG files from a folder (Ctrl+O)")
        self.addFolderBtn.setShortcut(QtGui.QKeySequence("Ctrl+O"))
        self.addFolderBtn.clicked.connect(self.add_folder_dialog)

        # --- Right: image panel (selected file) ---
        self.imageBox = QtWidgets.QGroupBox("Image")
        self.imageBox.setStyleSheet(
            "QGroupBox { font-weight: 600; }"
            "QGroupBox::title { subcontrol-origin: margin; left: 8px; padding: 0 6px; }"
        )
        imageLayout = QtWidgets.QVBoxLayout(self.imageBox)

        previewBox = QtWidgets.QWidget()
        previewLayout = QtWidgets.QVBoxLayout(previewBox)
        previewLayout.setContentsMargins(0, 0, 0, 0)
        previewLayout.addWidget(self.selectedLabel)
        dateRowW = QtWidgets.QWidget()
        dateRow = QtWidgets.QHBoxLayout(dateRowW)
        dateRow.setContentsMargins(0, 0, 0, 0)
        dateRow.addWidget(self.dateLabel, 1)
        dateRow.addWidget(self.copyDateBtn)
        previewLayout.addWidget(dateRowW)
        previewLayout.addWidget(self.previewLabel, 1)

        tagsBox = QtWidgets.QWidget()
        tagsLayout = QtWidgets.QVBoxLayout(tagsBox)
        tagsLayout.setContentsMargins(0, 0, 0, 0)
        mismatchRowW = QtWidgets.QWidget()
        mismatchRow = QtWidgets.QHBoxLayout(mismatchRowW)
        mismatchRow.setContentsMargins(0, 0, 0, 0)
        mismatchRow.addWidget(self.mismatchLabel, 1)
        mismatchRow.addWidget(self.resolveBtn)
        tagsLayout.addWidget(mismatchRowW)

        tagsLayout.addWidget(QtWidgets.QLabel("Tags on image"))
        tagsLayout.addWidget(self.keywordsList, 1)

        addRow = QtWidgets.QHBoxLayout()
        addRow.addWidget(self.addEdit, 1)
        addRow.addWidget(self.addBtn)
        addRow.addWidget(self.removeBtn)
        tagsLayout.addLayout(addRow)
        tagsLayout.addWidget(self.keepBackup)

        rightSplitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical)
        rightSplitter.addWidget(previewBox)
        rightSplitter.addWidget(tagsBox)
        rightSplitter.setStretchFactor(0, 2)
        rightSplitter.setStretchFactor(1, 1)
        rightSplitter.setChildrenCollapsible(False)
        imageLayout.addWidget(rightSplitter)

        # --- Left-bottom: repo panel (known tags) ---
        self.repoBox = QtWidgets.QGroupBox("Tag repo")
        self.repoBox.setStyleSheet(
            "QGroupBox { font-weight: 600; }"
            "QGroupBox::title { subcontrol-origin: margin; left: 8px; padding: 0 6px; }"
        )
        repoLayout = QtWidgets.QVBoxLayout(self.repoBox)
        repoLayout.addWidget(QtWidgets.QLabel("Known tags (recent + folder)"))

        knownFilterRowW = QtWidgets.QWidget()
        knownFilterRow = QtWidgets.QHBoxLayout(knownFilterRowW)
        knownFilterRow.setContentsMargins(0, 0, 0, 0)
        knownFilterRow.addWidget(self.knownFilter, 1)
        knownFilterRow.addWidget(self.knownRefreshBtn)
        repoLayout.addWidget(knownFilterRowW)
        repoLayout.addWidget(self.recursiveScan)
        repoLayout.addWidget(self.knownList, 1)

        filesPanel = QtWidgets.QWidget()
        filesLayout = QtWidgets.QVBoxLayout(filesPanel)
        filesLayout.setContentsMargins(0, 0, 0, 0)
        filesTopRow = QtWidgets.QHBoxLayout()
        filesTopRow.setContentsMargins(0, 0, 0, 0)
        filesTopRow.addWidget(self.onlyUntagged)
        filesTopRow.addWidget(self.filterInfoLabel)
        filesTopRow.addWidget(self.addFolderBtn)
        filesTopRow.addStretch(1)
        filesLayout.addLayout(filesTopRow)
        filesLayout.addWidget(self.files, 1)

        leftSplitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical)
        leftSplitter.addWidget(filesPanel)
        leftSplitter.addWidget(self.repoBox)
        leftSplitter.setStretchFactor(0, 3)
        leftSplitter.setStretchFactor(1, 2)
        leftSplitter.setChildrenCollapsible(False)
        leftSplitter.setMinimumWidth(250)

        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        splitter.addWidget(leftSplitter)
        splitter.addWidget(self.imageBox)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        splitter.setChildrenCollapsible(False)
        leftSplitter.setMinimumWidth(250)

        self.setCentralWidget(splitter)
        self.statusBar().showMessage("Ready")
        self.resize(1100, 700)
        splitter.setSizes([450, 650])

        self.cmdLine = QtWidgets.QLineEdit()
        self.cmdLine.setPlaceholderText(":")
        self.cmdLine.setVisible(False)
        self.cmdLine.returnPressed.connect(self._execute_command_line)
        self.statusBar().addWidget(self.cmdLine, 1)

        self._cmdHint = QtWidgets.QLabel(self)
        self._cmdHint.setVisible(False)
        self._cmdHint.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter)
        self._cmdHint.setStyleSheet(
            "QLabel { background: palette(window); border: 1px solid palette(mid); "
            "border-radius: 4px; padding: 2px 6px; }"
        )

        self._tagHint = QtWidgets.QLabel(self)
        self._tagHint.setVisible(False)
        self._tagHint.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter)
        self._tagHint.setStyleSheet(
            "QLabel { background: palette(window); border: 1px solid palette(mid); "
            "border-radius: 4px; padding: 2px 6px; }"
        )

        self._apply_focus_styles()

        # Make the whole window feel droppable (not only the file list).
        for w in [
            self,
            self.centralWidget(),
            splitter,
            leftSplitter,
            self.files,
            self.files.viewport(),
            filesPanel,
            self.repoBox,
            self.knownList,
            self.knownList.viewport(),
            self.imageBox,
            self.previewLabel,
            self.keywordsList,
            self.keywordsList.viewport(),
            self.addEdit,
            self.cmdLine,
        ]:
            if w is not None:
                w.setAcceptDrops(True)
                w.installEventFilter(self)

        self.refresh_known_tags()

        # Extra shortcuts (work regardless of focus)
        self._shortcuts: list[QtGui.QShortcut] = []
        self._vim_g_pending: dict[int, int] = {}
        self._vim_space_pending: int | None = None
        self._vim_visual_keywords = False
        self._vim_visual_anchor = 0
        self._yanked_tags: list[str] = []
        self._last_left_pane: QtWidgets.QListWidget = self.files
        self._commands: dict[str, Command] = {}
        self._command_list: list[Command] = []
        self._init_shortcuts()
        self._init_commands()

    def _init_shortcuts(self) -> None:
        sc = QtGui.QShortcut(QtGui.QKeySequence("Backspace"), self)
        sc.activated.connect(self.remove_selected_keywords)
        self._shortcuts.append(sc)

        sc = QtGui.QShortcut(QtGui.QKeySequence("Escape"), self)
        sc.activated.connect(self._escape_action)
        self._shortcuts.append(sc)

        for seq in ("Ctrl+Return", "Ctrl+Enter"):
            sc = QtGui.QShortcut(QtGui.QKeySequence(seq), self)
            sc.activated.connect(self.add_keyword_from_input)
            self._shortcuts.append(sc)

        sc = QtGui.QShortcut(QtGui.QKeySequence("Ctrl+F"), self)
        sc.activated.connect(self._focus_known_filter_select_all)
        self._shortcuts.append(sc)

        sc = QtGui.QShortcut(QtGui.QKeySequence("Ctrl+L"), self)
        sc.activated.connect(self._focus_add_edit_select_all)
        self._shortcuts.append(sc)

        sc = QtGui.QShortcut(QtGui.QKeySequence("Ctrl+Shift+B"), self)
        sc.activated.connect(self._toggle_keep_backup)
        self._shortcuts.append(sc)

        sc = QtGui.QShortcut(QtGui.QKeySequence("Ctrl+Shift+E"), self)
        sc.activated.connect(self._toggle_only_iptc_empty)
        self._shortcuts.append(sc)

        sc = QtGui.QShortcut(QtGui.QKeySequence("Ctrl+W, W"), self)
        sc.activated.connect(self._focus_next_pane)
        self._shortcuts.append(sc)

        sc = QtGui.QShortcut(QtGui.QKeySequence("Ctrl+W, Ctrl+W"), self)
        sc.activated.connect(self._focus_next_pane)
        self._shortcuts.append(sc)

        for key, direction in (("Ctrl+W, H", "left"), ("Ctrl+W, L", "right")):
            sc = QtGui.QShortcut(QtGui.QKeySequence(key), self)
            sc.activated.connect(lambda d=direction: self._focus_pane_by_direction(d))
            self._shortcuts.append(sc)

        for key, direction in (("Ctrl+W, J", "down"), ("Ctrl+W, K", "up")):
            sc = QtGui.QShortcut(QtGui.QKeySequence(key), self)
            sc.activated.connect(lambda d=direction: self._focus_pane_by_direction(d))
            self._shortcuts.append(sc)

        sc = QtGui.QShortcut(QtGui.QKeySequence("/"), self)
        sc.activated.connect(self._focus_known_filter_select_all)
        self._shortcuts.append(sc)

        sc = QtGui.QShortcut(QtGui.QKeySequence("n"), self)
        sc.activated.connect(lambda: self._move_list_selection(self.knownList, +1))
        self._shortcuts.append(sc)

        sc = QtGui.QShortcut(QtGui.QKeySequence("N"), self)
        sc.activated.connect(lambda: self._move_list_selection(self.knownList, -1))
        self._shortcuts.append(sc)

        sc = QtGui.QShortcut(QtGui.QKeySequence("l"), self.files)
        sc.setContext(QtCore.Qt.ShortcutContext.WidgetShortcut)
        sc.activated.connect(lambda: self._focus_pane(self.keywordsList))
        self._shortcuts.append(sc)

        sc = QtGui.QShortcut(QtGui.QKeySequence("h"), self.keywordsList)
        sc.setContext(QtCore.Qt.ShortcutContext.WidgetShortcut)
        sc.activated.connect(lambda: self._focus_pane(self._last_left_pane or self.files))
        self._shortcuts.append(sc)

        sc = QtGui.QShortcut(QtGui.QKeySequence("Shift+V"), self.keywordsList)
        sc.setContext(QtCore.Qt.ShortcutContext.WidgetShortcut)
        sc.activated.connect(self._toggle_visual_keywords)
        self._shortcuts.append(sc)

        sc = QtGui.QShortcut(QtGui.QKeySequence("Ctrl+C"), self.keywordsList)
        sc.setContext(QtCore.Qt.ShortcutContext.WidgetShortcut)
        sc.activated.connect(self._yank_selected_tags)
        self._shortcuts.append(sc)

        for lst in (self.files, self.keywordsList):
            sc = QtGui.QShortcut(QtGui.QKeySequence("Ctrl+V"), lst)
            sc.setContext(QtCore.Qt.ShortcutContext.WidgetShortcut)
            sc.activated.connect(self._paste_yanked_tags)
            self._shortcuts.append(sc)

    def _apply_focus_styles(self) -> None:
        list_qss = (
            "QListWidget { border: 1px solid palette(mid); border-radius: 4px; }"
            "QListWidget:focus { border: 1px solid #60a5fa; }"
        )
        edit_qss = (
            "QLineEdit { border: 1px solid palette(mid); border-radius: 4px; }"
            "QLineEdit:focus { border: 1px solid #60a5fa; }"
        )
        for lst in (self.files, self.keywordsList, self.knownList):
            lst.setStyleSheet(list_qss)
        for edit in (self.addEdit, self.knownFilter, self.cmdLine):
            edit.setStyleSheet(edit_qss)

    def eventFilter(self, obj: QtCore.QObject, event: QtCore.QEvent) -> bool:
        et = event.type()
        if obj is self.previewLabel and et == QtCore.QEvent.Type.Resize:
            self._update_preview_pixmap()
        if et in (
            QtCore.QEvent.Type.DragEnter,
            QtCore.QEvent.Type.DragMove,
        ):
            md = getattr(event, "mimeData", None)
            if callable(md) and event.mimeData().hasUrls():
                event.acceptProposedAction()
                return True
        if et == QtCore.QEvent.Type.Drop:
            md = getattr(event, "mimeData", None)
            if callable(md) and event.mimeData().hasUrls():
                paths = extract_image_paths_from_urls(event.mimeData().urls())
                if paths:
                    self.add_files(paths)
                    event.acceptProposedAction()
                    return True
        if et == QtCore.QEvent.Type.ShortcutOverride:
            if not isinstance(self.focusWidget(), QtWidgets.QLineEdit):
                if self._mods_ok(event.modifiers()):
                    if event.key() in (
                        QtCore.Qt.Key.Key_I,
                        QtCore.Qt.Key.Key_T,
                        QtCore.Qt.Key.Key_F,
                        QtCore.Qt.Key.Key_G,
                        QtCore.Qt.Key.Key_J,
                        QtCore.Qt.Key.Key_K,
                    ):
                        event.accept()
                        return True
        if et == QtCore.QEvent.Type.KeyPress:
            key = getattr(event, "key", None)
            if callable(key):
                if isinstance(self.focusWidget(), QtWidgets.QLineEdit):
                    pass
                else:
                    k = event.key()
                    if self._mods_ok(event.modifiers()):
                        if k == QtCore.Qt.Key.Key_I:
                            self._focus_add_edit_select_all()
                            return True
                        if k == QtCore.Qt.Key.Key_T:
                            self._focus_pane(self.knownList)
                            return True
                        if k == QtCore.Qt.Key.Key_F:
                            self._focus_pane(self.files)
                            return True

                        lst = self._list_from_obj(obj) or self._list_from_obj(self.focusWidget())
                        if lst is not None:
                            if k == QtCore.Qt.Key.Key_G:
                                if event.modifiers() & QtCore.Qt.KeyboardModifier.ShiftModifier:
                                    self._go_list_edge(lst, to_end=True)
                                else:
                                    self._vim_g(lst)
                                return True
                            if k == QtCore.Qt.Key.Key_J:
                                self._move_list_selection(lst, +1)
                                return True
                            if k == QtCore.Qt.Key.Key_K:
                                self._move_list_selection(lst, -1)
                                return True
                if event.text() == ":":
                    fw = self.focusWidget()
                    if not isinstance(fw, QtWidgets.QLineEdit):
                        self._open_command_line()
                        return True
                if obj is self.cmdLine and event.key() == QtCore.Qt.Key.Key_Tab:
                    self._tab_complete_command_line()
                    return True
                if obj is self.addEdit and event.key() == QtCore.Qt.Key.Key_Tab:
                    self._tab_complete_add_edit()
                    return True
        if obj in (self.addEdit, self.knownFilter):
            if event.type() == QtCore.QEvent.Type.KeyPress:
                if event.key() == QtCore.Qt.Key.Key_C and event.modifiers() == QtCore.Qt.KeyboardModifier.ControlModifier:
                    self._escape_action()
                    return True  # capture Event
        if et == QtCore.QEvent.Type.KeyPress and obj in (self.files, self.keywordsList, self.knownList):
            key = getattr(event, "key", None)
            if callable(key):
                k = event.key()
                now = int(QtCore.QDateTime.currentMSecsSinceEpoch())
                if k == QtCore.Qt.Key.Key_Space:
                    self._vim_space_pending = now
                    return True
                if k in (QtCore.Qt.Key.Key_Y, QtCore.Qt.Key.Key_P):
                    if self._vim_space_pending is not None and (now - self._vim_space_pending) <= 600:
                        self._vim_space_pending = None
                        if k == QtCore.Qt.Key.Key_Y and obj is self.keywordsList:
                            self._yank_selected_tags()
                            return True
                        if k == QtCore.Qt.Key.Key_P and obj in (self.files, self.keywordsList):
                            self._paste_yanked_tags()
                            return True
                if self._vim_space_pending is not None and (now - self._vim_space_pending) > 600:
                    self._vim_space_pending = None
        if et == QtCore.QEvent.Type.FocusIn:
            if obj in (self.files, self.knownList):
                self._last_left_pane = obj
        return super().eventFilter(obj, event)

    def _list_from_obj(self, obj: QtCore.QObject) -> QtWidgets.QListWidget | None:
        cur = obj
        while cur is not None:
            if cur in (self.files, self.knownList, self.keywordsList):
                return cur
            try:
                cur = cur.parent()
            except Exception:
                break
        return None

    def _mods_ok(self, mods: QtCore.Qt.KeyboardModifier) -> bool:
        allowed = QtCore.Qt.KeyboardModifier.ShiftModifier
        return (mods & ~allowed) == QtCore.Qt.KeyboardModifier.NoModifier

    def _move_list_selection(self, lst: QtWidgets.QListWidget, delta: int) -> None:
        if lst.count() == 0:
            return
        row = lst.currentRow()
        if row < 0:
            row = self._first_visible_row(lst) if delta >= 0 else self._last_visible_row(lst)
        else:
            row = self._next_visible_row(lst, row, delta)
        if row is None:
            return
        if lst is self.keywordsList and self._vim_visual_keywords:
            self._select_list_range(lst, self._vim_visual_anchor, row)
            lst.setCurrentRow(row)
        else:
            if lst is self.keywordsList:
                self._set_single_list_selection(lst, row)
            else:
                lst.setCurrentRow(row)
        lst.scrollToItem(lst.currentItem())

    def _go_list_edge(self, lst: QtWidgets.QListWidget, to_end: bool) -> None:
        if lst.count() == 0:
            return
        row = self._last_visible_row(lst) if to_end else self._first_visible_row(lst)
        if row is None:
            return
        if lst is self.keywordsList and not self._vim_visual_keywords:
            self._set_single_list_selection(lst, row)
        else:
            lst.setCurrentRow(row)
        lst.scrollToItem(lst.currentItem())

    def _first_visible_row(self, lst: QtWidgets.QListWidget) -> int | None:
        for i in range(lst.count()):
            it = lst.item(i)
            if it is not None and not it.isHidden():
                return i
        return None

    def _last_visible_row(self, lst: QtWidgets.QListWidget) -> int | None:
        for i in range(lst.count() - 1, -1, -1):
            it = lst.item(i)
            if it is not None and not it.isHidden():
                return i
        return None

    def _next_visible_row(self, lst: QtWidgets.QListWidget, start: int, delta: int) -> int | None:
        if delta == 0:
            return start
        step = 1 if delta > 0 else -1
        i = start + step
        while 0 <= i < lst.count():
            it = lst.item(i)
            if it is not None and not it.isHidden():
                return i
            i += step
        return start

    def _vim_g(self, lst: QtWidgets.QListWidget) -> None:
        key = id(lst)
        now = int(QtCore.QDateTime.currentMSecsSinceEpoch())
        last = self._vim_g_pending.get(key)
        if last is not None and (now - last) <= 600:
            self._vim_g_pending.pop(key, None)
            self._go_list_edge(lst, to_end=False)
            return
        self._vim_g_pending[key] = now

    def _escape_action(self) -> None:
        if self.cmdLine.isVisible():
            self._close_command_line()
            return
        fw = self.focusWidget()
        if isinstance(fw, QtWidgets.QLineEdit):
            fw.clearFocus()
            self.setFocus()
            return

    def _open_command_line(self) -> None:
        self.cmdLine.setVisible(True)
        self.cmdLine.setText(":")
        self.cmdLine.setCursorPosition(1)
        self.cmdLine.setFocus()
        self._hide_cmd_matches()

    def _close_command_line(self) -> None:
        self.cmdLine.setVisible(False)
        self.cmdLine.clear()
        self._hide_cmd_matches()
        self.setFocus()

    def _execute_command_line(self) -> None:
        raw = (self.cmdLine.text() or "").strip()
        self._close_command_line()
        if not raw:
            return
        if raw.startswith(":"):
            raw = raw[1:].strip()
        if not raw:
            return
        parts = raw.split()
        name = parts[0].casefold()
        args = parts[1:]
        self._run_command(name, args)

    def _tab_complete_command_line(self) -> None:
        raw = self.cmdLine.text() or ""
        if not raw.startswith(":"):
            return
        prefix = raw[1:].strip().casefold()
        if not prefix:
            return
        matches = self._command_candidates(prefix)
        if not matches:
            self.statusBar().showMessage("No command match")
            self._hide_cmd_matches()
            return
        common = self._common_prefix(matches)
        if common and common != prefix:
            self.cmdLine.setText(f":{common}")
            self.cmdLine.setCursorPosition(len(self.cmdLine.text()))
        if len(matches) == 1:
            self.cmdLine.setText(f":{matches[0]} ")
            self.cmdLine.setCursorPosition(len(self.cmdLine.text()))
            self._hide_cmd_matches()
            return
        self._show_cmd_matches(", ".join(matches))

    def _tab_complete_add_edit(self) -> None:
        raw = (self.addEdit.text() or "").strip()
        if not raw:
            return
        matches = self._tag_candidates(raw)
        if not matches:
            self.statusBar().showMessage("No tag match")
            self._hide_tag_matches()
            return
        common = self._common_prefix(matches)
        if common and common.casefold() != raw.casefold():
            self.addEdit.setText(common)
            self.addEdit.setCursorPosition(len(common))
        if len(matches) == 1:
            self.addEdit.setText(matches[0])
            self.addEdit.setCursorPosition(len(matches[0]))
            self._hide_tag_matches()
            return
        self._show_tag_matches(", ".join(matches))

    def _command_candidates(self, prefix: str) -> list[str]:
        names = {cmd.name for cmd in self._command_list}
        for cmd in self._command_list:
            names.update(cmd.aliases)
        out = [n for n in names if n.startswith(prefix)]
        out.sort()
        return out

    def _tag_candidates(self, prefix: str) -> list[str]:
        prefix_cf = prefix.casefold()
        names: list[str] = []
        for i in range(self.knownList.count()):
            it = self.knownList.item(i)
            if it is None:
                continue
            txt = (it.text() or "").strip()
            if not txt:
                continue
            if txt.casefold().startswith(prefix_cf):
                names.append(txt)
        names = dedupe_casefold(names)
        names.sort(key=lambda s: s.casefold())
        return names

    def _common_prefix(self, items: list[str]) -> str:
        if not items:
            return ""
        pref = items[0]
        for s in items[1:]:
            i = 0
            lim = min(len(pref), len(s))
            while i < lim and pref[i] == s[i]:
                i += 1
            pref = pref[:i]
            if not pref:
                break
        return pref

    def _show_cmd_matches(self, text: str) -> None:
        self._cmdHint.setText(text)
        self._cmdHint.setVisible(True)
        self._position_cmd_hint()

    def _hide_cmd_matches(self) -> None:
        self._cmdHint.setVisible(False)

    def _show_tag_matches(self, text: str) -> None:
        self._tagHint.setText(text)
        self._tagHint.setVisible(True)
        self._position_tag_hint()

    def _hide_tag_matches(self) -> None:
        self._tagHint.setVisible(False)

    def _position_cmd_hint(self) -> None:
        if not self._cmdHint.isVisible():
            return
        sb = self.statusBar()
        if sb is None:
            return
        sb_geo = sb.geometry()
        margin = 6
        height = self._cmdHint.sizeHint().height() + 4
        width = sb_geo.width() - margin * 2
        x = sb_geo.x() + margin
        y = sb_geo.y() - height - 4
        self._cmdHint.setGeometry(x, y, max(10, width), height)

    def _position_tag_hint(self) -> None:
        if not self._tagHint.isVisible():
            return
        edit_geo = self.addEdit.geometry()
        map_pos = self.addEdit.mapTo(self, QtCore.QPoint(0, 0))
        margin = 6
        height = self._tagHint.sizeHint().height() + 4
        width = max(10, edit_geo.width() - margin * 2)
        x = map_pos.x() + margin
        y = map_pos.y() - height - 4
        self._tagHint.setGeometry(x, y, width, height)

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:
        super().resizeEvent(event)
        self._position_cmd_hint()
        self._position_tag_hint()
        self._update_preview_pixmap()

    def _register_command(
        self,
        name: str,
        callback,
        description: str,
        shortcuts: list[str] | None = None,
        aliases: list[str] | None = None,
    ) -> None:
        cmd = Command(
            name=name,
            callback=callback,
            description=description,
            shortcuts=shortcuts or [],
            aliases=aliases or [],
        )
        self._commands[name] = cmd
        for a in cmd.aliases:
            self._commands[a] = cmd
        self._command_list.append(cmd)

    def _run_command(self, name: str, args: list[str]) -> None:
        cmd = self._commands.get(name)
        if cmd is None:
            self.statusBar().showMessage(f"Unknown command: {name}")
            return
        try:
            cmd.callback(args)
        except Exception as e:
            self._show_error(str(e))

    def _init_commands(self) -> None:
        self._register_command(
            "listcommands",
            self._cmd_list_commands,
            "List all commands",
            shortcuts=[":listcommands", ":ls"],
            aliases=["ls"],
        )
        self._register_command(
            "quit",
            self._cmd_quit,
            "Quit the app",
            shortcuts=[":quit", ":q"],
            aliases=["q"],
        )
        self._register_command(
            "addfolder",
            lambda _a: self.add_folder_dialog(),
            "Add files from a folder",
            shortcuts=["Ctrl+O"],
        )
        self._register_command(
            "refresh",
            lambda _a: self.force_refresh_known_tags(),
            "Refresh known tags",
            shortcuts=["F5"],
        )
        self._register_command(
            "resolve",
            lambda _a: self.resolve_mismatch(),
            "Resolve IPTC/XMP mismatch",
            shortcuts=["Ctrl+R"],
        )
        self._register_command(
            "addtag",
            lambda _a: self.add_keyword_from_input(),
            "Add tag from input",
            shortcuts=["Ctrl+Enter", "Ctrl+Return"],
        )
        self._register_command(
            "removetags",
            lambda _a: self.remove_selected_keywords(),
            "Remove selected tags",
            shortcuts=["Backspace", "Del"],
        )
        self._register_command(
            "focusfilter",
            lambda _a: self._focus_known_filter_select_all(),
            "Focus known-tag filter",
            shortcuts=["Ctrl+F", "/"],
        )
        self._register_command(
            "focusadd",
            lambda _a: self._focus_add_edit_select_all(),
            "Focus add-keyword input",
            shortcuts=["Ctrl+L", "i"],
        )
        self._register_command(
            "focusfiles",
            lambda _a: self._focus_pane(self.files),
            "Focus files pane",
            shortcuts=["f"],
        )
        self._register_command(
            "focustags",
            lambda _a: self._focus_pane(self.knownList),
            "Focus known-tags pane",
            shortcuts=["t"],
        )
        self._register_command(
            "togglebackup",
            lambda _a: self._toggle_keep_backup(),
            "Toggle keep *_original backups",
            shortcuts=["Ctrl+Shift+B"],
        )
        self._register_command(
            "toggleemptyiptc",
            lambda _a: self._toggle_only_iptc_empty(),
            "Toggle only IPTC-empty filter",
            shortcuts=["Ctrl+Shift+E"],
        )
        self._register_command(
            "panenext",
            lambda _a: self._focus_next_pane(),
            "Focus next pane",
            shortcuts=["Ctrl+W W", "Ctrl+W Ctrl+W"],
        )
        self._register_command(
            "paneleft",
            lambda _a: self._focus_pane_by_direction("left"),
            "Focus left pane",
            shortcuts=["Ctrl+W H", "h"],
        )
        self._register_command(
            "paneright",
            lambda _a: self._focus_pane_by_direction("right"),
            "Focus right pane",
            shortcuts=["Ctrl+W L", "l"],
        )
        self._register_command(
            "panedown",
            lambda _a: self._focus_pane_by_direction("down"),
            "Focus lower pane",
            shortcuts=["Ctrl+W J"],
        )
        self._register_command(
            "paneup",
            lambda _a: self._focus_pane_by_direction("up"),
            "Focus upper pane",
            shortcuts=["Ctrl+W K"],
        )
        self._register_command(
            "listdown",
            lambda _a: self._move_list_selection(self._current_list_widget(), +1),
            "Move selection down",
            shortcuts=["j", "Down"],
        )
        self._register_command(
            "listup",
            lambda _a: self._move_list_selection(self._current_list_widget(), -1),
            "Move selection up",
            shortcuts=["k", "Up"],
        )
        self._register_command(
            "listtop",
            lambda _a: self._go_list_edge(self._current_list_widget(), to_end=False),
            "Jump to top of list",
            shortcuts=["gg", "Home"],
        )
        self._register_command(
            "listbottom",
            lambda _a: self._go_list_edge(self._current_list_widget(), to_end=True),
            "Jump to bottom of list",
            shortcuts=["G", "End"],
        )
        self._register_command(
            "knownnext",
            lambda _a: self._move_list_selection(self.knownList, +1),
            "Next known-tag match",
            shortcuts=["n"],
        )
        self._register_command(
            "knownprev",
            lambda _a: self._move_list_selection(self.knownList, -1),
            "Previous known-tag match",
            shortcuts=["N"],
        )
        self._register_command(
            "visual",
            lambda _a: self._toggle_visual_keywords(),
            "Toggle visual tag selection",
            shortcuts=["Shift+V"],
        )
        self._register_command(
            "yank",
            lambda _a: self._yank_selected_tags(),
            "Yank selected tags",
            shortcuts=["Ctrl+C", "Space+y"],
        )
        self._register_command(
            "paste",
            lambda _a: self._paste_yanked_tags(),
            "Paste yanked tags",
            shortcuts=["Ctrl+V", "Space+p"],
        )
        self._register_command(
            "escape",
            lambda _a: self._escape_action(),
            "Reset focus / close command line",
            shortcuts=["Esc", "Ctrl+C"],
        )

    def _cmd_list_commands(self, _args: list[str]) -> None:
        lines: list[str] = []
        for cmd in sorted(self._command_list, key=lambda c: c.name):
            alias = f" (aliases: {', '.join(cmd.aliases)})" if cmd.aliases else ""
            shorts = f" [{', '.join(cmd.shortcuts)}]" if cmd.shortcuts else ""
            lines.append(f"{cmd.name}{alias} — {cmd.description}{shorts}")
        text = "\n".join(lines) if lines else "(no commands)"
        QtWidgets.QMessageBox.information(self, "Commands", text)

    def _cmd_quit(self, _args: list[str]) -> None:
        self.close()

    def _current_list_widget(self) -> QtWidgets.QListWidget:
        fw = self.focusWidget()
        if fw in (self.files, self.keywordsList, self.knownList):
            return fw
        return self.files

    def _set_single_list_selection(self, lst: QtWidgets.QListWidget, row: int) -> None:
        if row < 0 or row >= lst.count():
            return
        item = lst.item(row)
        if item is None:
            return
        lst.blockSignals(True)
        try:
            lst.clearSelection()
            item.setSelected(True)
            lst.setCurrentItem(item)
        finally:
            lst.blockSignals(False)

    def _toggle_visual_keywords(self) -> None:
        if self.keywordsList.count() == 0:
            return
        self._vim_visual_keywords = not self._vim_visual_keywords
        if self.keywordsList.currentRow() < 0:
            self._set_single_list_selection(self.keywordsList, 0)
        self._vim_visual_anchor = self.keywordsList.currentRow()
        if self._vim_visual_keywords:
            self.keywordsList.setSelectionMode(
                QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection
            )
            self._select_list_range(self.keywordsList, self._vim_visual_anchor, self._vim_visual_anchor)
        else:
            self.keywordsList.setSelectionMode(
                QtWidgets.QAbstractItemView.SelectionMode.SingleSelection
            )
            self._set_single_list_selection(self.keywordsList, self._vim_visual_anchor)

    def _select_list_range(self, lst: QtWidgets.QListWidget, start: int, end: int) -> None:
        a = max(0, min(start, end))
        b = min(lst.count() - 1, max(start, end))
        lst.blockSignals(True)
        try:
            lst.clearSelection()
            for i in range(a, b + 1):
                it = lst.item(i)
                if it is not None:
                    it.setSelected(True)
        finally:
            lst.blockSignals(False)

    def _yank_selected_tags(self) -> None:
        items = self.keywordsList.selectedItems()
        tags = [it.text().strip() for it in items if it is not None and it.text().strip()]
        tags = dedupe_casefold(tags)
        if not tags:
            self.statusBar().showMessage("No tags selected")
            return
        self._yanked_tags = tags
        self.statusBar().showMessage(f"Yanked {len(tags)} tag(s)")

    def _paste_yanked_tags(self) -> None:
        if not self._yanked_tags:
            self.statusBar().showMessage("Yank tags first")
            return
        files = self.selected_file_paths()
        if not files:
            self.statusBar().showMessage("No files selected")
            return
        target = files[0]
        try:
            result = self.tag_mutations.add_tags(
                [target],
                self._yanked_tags,
                keep_backup=self.keepBackup.isChecked(),
                load_state=self._ensure_loaded,
            )
            self._apply_tag_mutation_result(result)
            self.statusBar().showMessage(f"Pasted {len(self._yanked_tags)} tag(s)")
        except ExifToolError as e:
            self._show_error(str(e))

    def _focus_pane(self, pane: QtWidgets.QListWidget) -> None:
        if pane.count() > 0 and pane.currentRow() < 0:
            if pane is self.keywordsList and not self._vim_visual_keywords:
                self._set_single_list_selection(pane, 0)
            else:
                pane.setCurrentRow(0)
        elif pane is self.keywordsList and not self._vim_visual_keywords and pane.currentRow() >= 0:
            self._set_single_list_selection(pane, pane.currentRow())
        pane.setFocus()

    def _focus_next_pane(self) -> None:
        panes = [self.files, self.knownList, self.keywordsList]
        focus = self.focusWidget()
        current = None
        for p in panes:
            if focus is p:
                current = p
                break
        if current is None:
            self._focus_pane(panes[0])
            return
        idx = panes.index(current)
        nxt = panes[(idx + 1) % len(panes)]
        self._focus_pane(nxt)

    def _focus_pane_by_direction(self, direction: str) -> None:
        # NOTE: If pane layout grows more complex, revisit shortcut coherence.
        focus = self.focusWidget()
        current = focus if focus in (self.files, self.knownList, self.keywordsList) else None
        if current is None:
            self._focus_pane(self.files)
            return

        if direction == "left":
            if current is self.keywordsList:
                self._focus_pane(self._last_left_pane or self.files)
            return

        if direction == "right":
            if current in (self.files, self.knownList):
                self._focus_pane(self.keywordsList)
            return

        if direction == "down":
            if current is self.files:
                self._focus_pane(self.knownList)
            elif current is self.keywordsList:
                self._focus_pane(self.knownList)
            return

        if direction == "up":
            if current is self.knownList:
                self._focus_pane(self.files)
            elif current is self.keywordsList:
                self._focus_pane(self.files)
            return

    # Fallback handlers: some widgets won't forward drag events to the filter.
    def dragEnterEvent(self, event: QtGui.QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event: QtGui.QDragMoveEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event: QtGui.QDropEvent) -> None:
        if event.mimeData().hasUrls():
            paths = extract_image_paths_from_urls(event.mimeData().urls())
            if paths:
                self.add_files(paths)
                event.acceptProposedAction()
                return
        super().dropEvent(event)

    def add_files(self, paths: list[str]) -> None:
        seen = set(self.all_file_paths())
        added = 0
        last_added_path = None
        for p in paths:
            p2 = normalize_path(p)
            if p2 in seen:
                continue
            self.files.addItem(p2)
            seen.add(p2)
            added += 1
            last_added_path = p2
        self.statusBar().showMessage(f"Added {added} files")
        if added and not self.files.selectedItems():
            self.files.setCurrentRow(0)
        if self.onlyUntagged.isChecked():
            self.apply_iptc_filter_async()
        if last_added_path:
            self._set_last_folder(str(Path(last_added_path).parent))

    def add_folder_dialog(self) -> None:
        default_dir = self._get_default_folder_for_dialog()
        if default_dir:
            folder = QtWidgets.QFileDialog.getExistingDirectory(
                self, "Choose folder", default_dir
            )
        else:
            folder = QtWidgets.QFileDialog.getExistingDirectory(self, "Choose folder")
        if not folder:
            return
        p = Path(folder)
        paths = [str(x) for x in p.rglob("*") if x.is_file() and x.suffix.lower() in SUPPORTED_EXTS]
        if paths:
            self.add_files(paths)
        self._set_last_folder(folder)
        if self.files.count() > 0:
            self.files.setFocus()
            if self.files.currentRow() < 0:
                self.files.setCurrentRow(0)

    def _set_last_folder(self, folder: str) -> None:
        try:
            p = Path(folder).resolve()
        except Exception:
            p = Path(folder)
        if not p.exists() or not p.is_dir():
            return
        self._config["last_folder"] = str(p)
        save_config(self._config)

    def _get_default_folder_for_dialog(self) -> str | None:
        last_folder = self._config.get("last_folder")
        if isinstance(last_folder, str) and last_folder:
            try:
                p = Path(last_folder)
                if p.exists() and p.is_dir():
                    return str(p)
            except Exception:
                pass

        sel = self.selected_file_paths()
        if sel:
            try:
                return str(Path(sel[0]).resolve().parent)
            except Exception:
                return str(Path(sel[0]).parent)

        if self.files.count() > 0:
            try:
                return str(Path(self.files.item(0).text()).resolve().parent)
            except Exception:
                return str(Path(self.files.item(0).text()).parent)
        return None

    def all_file_paths(self) -> list[str]:
        return [self.files.item(i).text() for i in range(self.files.count())]

    def selected_file_paths(self) -> list[str]:
        return [it.text() for it in self.files.selectedItems()]

    def _ensure_loaded(self, path: str) -> KeywordState:
        st = self._keywords_cache.get(path)
        if st is None:
            st = self.exif.read_keywords(path)
            self._keywords_cache[path] = st
        return st

    def on_selection_changed(self) -> None:
        sel = self.selected_file_paths()
        if not sel:
            if self.onlyUntagged.isChecked():
                self._sync_filter_preserved_selection([])
            self.selectedLabel.setText("Drop JPG/JPEG files here")
            self.mismatchLabel.setText("")
            self.resolveBtn.setEnabled(False)
            self.keywordsList.clear()
            self.dateLabel.setText("")
            self.previewLabel.setText("No preview")
            self.previewLabel.setPixmap(QtGui.QPixmap())
            self.refresh_known_tags()
            return

        current = sel[0]
        self.selectedLabel.setText(current)
        self.resolveBtn.setEnabled(False)
        self._load_preview_async(current)

        self._selection_token += 1
        token = self._selection_token
        self.statusBar().showMessage("Reading keywords...")

        if self.onlyUntagged.isChecked():
            self._sync_filter_preserved_selection(sel)

        worker = Worker(self.exif.read_keywords, current)

        def _ok(st: KeywordState) -> None:
            if token != self._selection_token:
                return
            self._keywords_cache[current] = st
            self._render_keywords(st)
            if st.date_display:
                self.dateLabel.setText(f"Capture date: {st.date_display}")
            else:
                self.dateLabel.setText("Capture date: (missing)")
            self.statusBar().showMessage("Ready")
            self.refresh_known_tags()

        def _err(msg: str) -> None:
            if token != self._selection_token:
                return
            self.statusBar().showMessage("Error")
            self._show_error(msg)

        worker.signals.finished.connect(_ok)
        worker.signals.error.connect(_err)
        self.pool.start(worker)

    def _load_preview_async(self, path: str) -> None:
        self._preview_token += 1
        token = self._preview_token
        self.previewLabel.setText("Loading preview...")
        self.previewLabel.setPixmap(QtGui.QPixmap())
        self._preview_image = None

        def _work(p: str) -> QtGui.QImage:
            reader = QtGui.QImageReader(p)
            reader.setAutoTransform(True)
            img = reader.read()
            if img.isNull():
                raise RuntimeError("Failed to load image preview")
            return img

        worker = Worker(_work, path)

        def _ok(img: QtGui.QImage) -> None:
            if token != self._preview_token:
                return
            self._preview_image = img
            self._update_preview_pixmap()
            self.previewLabel.setText("")

        def _err(msg: str) -> None:
            if token != self._preview_token:
                return
            self.previewLabel.setText("No preview")
            self.previewLabel.setPixmap(QtGui.QPixmap())
            self._preview_image = None

        worker.signals.finished.connect(_ok)
        worker.signals.error.connect(_err)
        self.pool.start(worker)

    def _update_preview_pixmap(self) -> None:
        if self._preview_image is None:
            return
        img = self._preview_image
        max_w = max(1, self.previewLabel.width() - 16)
        max_h = max(1, self.previewLabel.height() - 16)
        if img.width() > max_w or img.height() > max_h:
            scaled = img.scaled(
                max_w,
                max_h,
                QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                QtCore.Qt.TransformationMode.SmoothTransformation,
            )
            pm = QtGui.QPixmap.fromImage(scaled)
        else:
            pm = QtGui.QPixmap.fromImage(img)
        self.previewLabel.setPixmap(pm)

    def _render_keywords(self, st: KeywordState) -> None:
        self._vim_visual_keywords = False
        self.keywordsList.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.keywordsList.clear()
        for kw in st.merged:
            self.keywordsList.addItem(kw)
        if self.keywordsList.count() > 0:
            self._set_single_list_selection(self.keywordsList, 0)
        if st.mismatch:
            self.mismatchLabel.setText(
                "Warning: IPTC:Keywords and XMP-dc:Subject differ (showing merged view)"
            )
            self.resolveBtn.setEnabled(True)
        else:
            self.mismatchLabel.setText("")
            self.resolveBtn.setEnabled(False)

    def _preserve_files_scroll(self, fn) -> None:
        view = self.files
        sb = view.verticalScrollBar()
        top_item = view.itemAt(0, 0)
        top_path = normalize_path(top_item.text()) if top_item is not None else None
        top_offset = view.visualItemRect(top_item).top() if top_item is not None else 0
        top_row = view.row(top_item) if top_item is not None else 0

        fn()

        if top_path:
            item = self._find_item_by_path(top_path)
            if item is None or item.isHidden():
                item = None
                for i in range(max(0, top_row), view.count()):
                    cand = view.item(i)
                    if cand is not None and not cand.isHidden():
                        item = cand
                        break
            if item is not None:
                view.scrollToItem(item, QtWidgets.QAbstractItemView.ScrollHint.PositionAtTop)
                sb.setValue(sb.value() + top_offset)

    def _ensure_files_focus_visible(self) -> None:
        if self.files.count() == 0:
            return
        hidden_selected = [it for it in self.files.selectedItems() if it.isHidden()]
        for it in hidden_selected:
            it.setSelected(False)
        current = self.files.currentItem()
        selected_visible = [it for it in self.files.selectedItems() if not it.isHidden()]
        if selected_visible:
            target = current if current in selected_visible else selected_visible[0]
            self.files.setCurrentItem(target)
            self.files.scrollToItem(target)
            self.files.setFocus()
            return
        for i in range(self.files.count()):
            it = self.files.item(i)
            if it is not None and not it.isHidden():
                self.files.clearSelection()
                it.setSelected(True)
                self.files.setCurrentItem(it)
                self.files.scrollToItem(it)
                self.files.setFocus()
                return

    def apply_iptc_filter_async(self, reset_preserved: bool = False) -> None:
        self._filter_token += 1
        token = self._filter_token
        if reset_preserved:
            self._filter_preserved = set()
        if not self.onlyUntagged.isChecked():
            for i in range(self.files.count()):
                self.files.item(i).setHidden(False)
                self.files.item(i).setBackground(QtGui.QBrush())
            self.filterInfoLabel.setText("")
            return

        paths = self.all_file_paths()
        if not paths:
            return

        # Build map, but keep list visible until first chunk completes.
        self._filter_map = {}
        for i in range(self.files.count()):
            it = self.files.item(i)
            it.setHidden(False)
            self._filter_map[normalize_path(it.text())] = it

        self._filter_total = self.files.count()
        self._filter_shown = 0
        self._filter_processed = 0
        self._filter_first_chunk = True
        self._filter_switched = False
        self.filterInfoLabel.setText(f"…/{self._filter_total}")

        # First chunk ~ a few screens; rest uses larger chunks.
        row_h = self.files.sizeHintForRow(0) or self.files.fontMetrics().height() + 4
        visible_rows = max(10, int(self.files.viewport().height() / max(1, row_h)))
        first_chunk_size = max(20, visible_rows * 2)
        chunk_size = 80
        first = paths[:first_chunk_size]
        rest = paths[first_chunk_size:]
        self._filter_queue = [first] if first else []
        if rest:
            self._filter_queue.extend(
                [rest[i : i + chunk_size] for i in range(0, len(rest), chunk_size)]
            )
        self.statusBar().showMessage("Filtering IPTC-empty...")
        self._process_next_filter_chunk(token)

    def _process_next_filter_chunk(self, token: int) -> None:
        if token != self._filter_token:
            return
        if not self._filter_queue:
            if self.onlyUntagged.isChecked() and not self._filter_switched:
                def _do_finish_empty():
                    for it in self._filter_map.values():
                        it.setHidden(True)
                    self._ensure_files_focus_visible()
                self._preserve_files_scroll(_do_finish_empty)
                self.filterInfoLabel.setText(f"0/{self._filter_total}")
            self.statusBar().showMessage("Ready")
            return

        chunk = self._filter_queue.pop(0)
        worker = Worker(self.exif.scan_iptc_empty, chunk)

        def _ok(empty: set[str]) -> None:
            if token != self._filter_token:
                return
            empty_norm = {normalize_path(p) for p in empty}
            empty_norm |= self._filter_preserved
            if self._filter_first_chunk:
                if empty_norm:
                    # Switch to filtered view only when we have first results.
                    self._filter_switched = True
                    def _do_first():
                        for it in self._filter_map.values():
                            it.setHidden(True)
                        for p in empty_norm:
                            it = self._filter_map.get(p)
                            if it is not None:
                                it.setHidden(False)
                                self._filter_shown += 1
                        self._ensure_files_focus_visible()
                    self._preserve_files_scroll(_do_first)
                self._filter_first_chunk = False
            else:
                if not self._filter_switched and empty_norm:
                    self._filter_switched = True
                    def _do_switch():
                        for it in self._filter_map.values():
                            it.setHidden(True)
                        for p in empty_norm:
                            it = self._filter_map.get(p)
                            if it is not None:
                                it.setHidden(False)
                                self._filter_shown += 1
                        self._ensure_files_focus_visible()
                    self._preserve_files_scroll(_do_switch)
                elif self._filter_switched:
                    def _do_next():
                        for p in empty_norm:
                            it = self._filter_map.get(p)
                            if it is not None and it.isHidden():
                                it.setHidden(False)
                                self._filter_shown += 1
                    self._preserve_files_scroll(_do_next)
            self._filter_processed += len(chunk)
            if self._filter_switched:
                self.filterInfoLabel.setText(f"{self._filter_shown}/{self._filter_total}")
            else:
                self.filterInfoLabel.setText(f"…/{self._filter_total}")
            self.statusBar().showMessage(
                f"Filtering IPTC-empty... {self._filter_processed}/{self._filter_total}"
            )
            QtCore.QTimer.singleShot(0, lambda: self._process_next_filter_chunk(token))

        def _err(msg: str) -> None:
            if token != self._filter_token:
                return
            self.statusBar().showMessage("Error")
            self._show_error(msg)
            self.filterInfoLabel.setText("")

        worker.signals.finished.connect(_ok)
        worker.signals.error.connect(_err)
        self.pool.start(worker)

    def _refresh_current_keywords_view_from_cache(self) -> None:
        sel = self.selected_file_paths()
        if not sel:
            return
        current = sel[0]
        st = self._keywords_cache.get(current)
        if st is None:
            return
        self._render_keywords(st)
        if st.date_display:
            self.dateLabel.setText(f"Capture date: {st.date_display}")
        else:
            self.dateLabel.setText("Capture date: (missing)")

    def _apply_tag_mutation_result(self, result: TagMutationResult) -> None:
        self._keywords_cache.update(result.updated_states)
        self._refresh_current_keywords_view_from_cache()
        self._apply_filter_visibility_changes(result.emptiness_by_path)

    def _find_item_by_path(self, path: str) -> QtWidgets.QListWidgetItem | None:
        target = normalize_path(path)
        for i in range(self.files.count()):
            it = self.files.item(i)
            if normalize_path(it.text()) == target:
                return it
        return None

    def _update_filter_label(self) -> None:
        if not self.onlyUntagged.isChecked():
            self.filterInfoLabel.setText("")
            return
        total = self.files.count()
        shown = 0
        for i in range(self.files.count()):
            if not self.files.item(i).isHidden():
                shown += 1
        self.filterInfoLabel.setText(f"{shown}/{total}")

    def _sync_filter_preserved_selection(self, selected_paths: list[str]) -> None:
        if not self.onlyUntagged.isChecked() or not self._filter_preserved:
            return
        selected = {normalize_path(p) for p in selected_paths}
        released = self._filter_preserved - selected
        if released:
            def _do():
                for path in released:
                    it = self._find_item_by_path(path)
                    if it is None:
                        continue
                    st = self._keywords_cache.get(path)
                    if st is not None:
                        it.setHidden(len(st.iptc) > 0)
            self._preserve_files_scroll(_do)
        self._filter_preserved &= selected

    def _apply_filter_visibility_changes(self, emptiness_by_path: dict[str, bool]) -> None:
        if not self.onlyUntagged.isChecked():
            return
        def _do():
            for path, is_empty in emptiness_by_path.items():
                it = self._find_item_by_path(path)
                if it is None:
                    continue
                if normalize_path(path) in self._filter_preserved:
                    it.setHidden(False)
                else:
                    it.setHidden(not is_empty)
        self._preserve_files_scroll(_do)
        self._ensure_files_focus_visible()
        self._update_filter_label()

    def add_keyword_from_input(self) -> None:
        tag = self.addEdit.text().strip()
        self.addEdit.clear()
        if not tag:
            return
        self._apply_add_tag(tag)

    def add_keyword_from_known(self, item=None) -> None:
        it = item if isinstance(item, QtWidgets.QListWidgetItem) else self.knownList.currentItem()
        if it is None:
            return
        tag = (it.text() or "").strip()
        if not tag:
            return
        self._apply_add_tag(tag)

    def _apply_add_tag(self, tag: str) -> None:
        files = self.selected_file_paths()
        if not files:
            self.statusBar().showMessage("No files selected")
            return
        if self.onlyUntagged.isChecked():
            self._filter_preserved = {normalize_path(p) for p in files}

        try:
            result = self.tag_mutations.add_tag(
                files,
                tag,
                keep_backup=self.keepBackup.isChecked(),
                load_state=self._ensure_loaded,
            )
        except ExifToolError as e:
            self._show_error(str(e))
            return

        add_recent_tag(tag)
        self._apply_tag_mutation_result(result)
        self.statusBar().showMessage(f"Added '{tag}' to {len(files)} file(s)")

    def remove_selected_keywords(self) -> None:
        files = self.selected_file_paths()
        if not files:
            self.statusBar().showMessage("No files selected")
            return
        if self.onlyUntagged.isChecked():
            self._filter_preserved = {normalize_path(p) for p in files}
        items = self.keywordsList.selectedItems()
        if not items:
            self.statusBar().showMessage("No keywords selected")
            return
        remove = {it.text().strip().casefold() for it in items if it.text().strip()}
        if not remove:
            return

        try:
            result = self.tag_mutations.remove_tags(
                files,
                remove,
                keep_backup=self.keepBackup.isChecked(),
                load_state=self._ensure_loaded,
            )
        except ExifToolError as e:
            self._show_error(str(e))
            return

        self._apply_tag_mutation_result(result)
        self.statusBar().showMessage(f"Removed {len(remove)} tag(s) from {len(files)} file(s)")

    def force_refresh_known_tags(self) -> None:
        sel = self.selected_file_paths()
        if sel:
            folder = str(Path(sel[0]).resolve().parent)
            key = (folder, self.recursiveScan.isChecked())
            self._folder_tag_cache.pop(key, None)
            self._folder_scans_inflight.discard(key)
        self.refresh_known_tags()

    def refresh_known_tags(self) -> None:
        filter_text = (self.knownFilter.text() or "").strip().casefold()
        recent = load_recent_tags()

        folder_tags: set[str] = set()
        sel = self.selected_file_paths()
        if sel:
            folder = str(Path(sel[0]).resolve().parent)
            key = (folder, self.recursiveScan.isChecked())
            cached = self._folder_tag_cache.get(key)
            if cached is None:
                self._ensure_folder_scan(folder, self.recursiveScan.isChecked())
                cached = set()
            folder_tags = cached

        combined = []
        seen_lower: set[str] = set()
        for t in recent:
            tl = t.casefold()
            if tl in seen_lower:
                continue
            seen_lower.add(tl)
            combined.append(t)
        for t in sorted(folder_tags, key=lambda s: s.casefold()):
            tl = t.casefold()
            if tl in seen_lower:
                continue
            seen_lower.add(tl)
            combined.append(t)

        if filter_text:
            combined = [t for t in combined if filter_text in t.casefold()]

        self.knownList.clear()
        for t in combined:
            self.knownList.addItem(t)

    def _focus_first_known_tag(self) -> None:
        if self.knownList.count() == 0:
            return
        self.knownList.setCurrentRow(0)
        self.knownList.setFocus()

    def _focus_known_filter_select_all(self) -> None:
        self.knownFilter.setFocus()
        self.knownFilter.selectAll()

    def _focus_add_edit_select_all(self) -> None:
        self.addEdit.setFocus()
        self.addEdit.selectAll()

    def _toggle_keep_backup(self) -> None:
        self.keepBackup.setChecked(not self.keepBackup.isChecked())
        state = "ON" if self.keepBackup.isChecked() else "OFF"
        self.statusBar().showMessage(f"Keep *_original backups: {state}")

    def _toggle_only_iptc_empty(self) -> None:
        self.onlyUntagged.setChecked(not self.onlyUntagged.isChecked())
        state = "ON" if self.onlyUntagged.isChecked() else "OFF"
        self.statusBar().showMessage(f"Only IPTC-empty: {state}")

    def _ensure_folder_scan(self, folder: str, recursive: bool) -> None:
        key = (folder, recursive)
        if key in self._folder_tag_cache:
            return
        if key in self._folder_scans_inflight:
            return
        self._folder_scans_inflight.add(key)

        token = self._selection_token
        self.statusBar().showMessage("Scanning folder tags...")
        worker = Worker(self.exif.scan_folder_tags, folder, recursive)

        def _ok(tags: set[str]) -> None:
            self._folder_tag_cache[key] = tags
            self._folder_scans_inflight.discard(key)
            if token == self._selection_token:
                self.statusBar().showMessage("Ready")
                self.refresh_known_tags()

        def _err(msg: str) -> None:
            self._folder_tag_cache[key] = set()
            self._folder_scans_inflight.discard(key)
            if token == self._selection_token:
                self.statusBar().showMessage("Ready")

        worker.signals.finished.connect(_ok)
        worker.signals.error.connect(_err)
        self.pool.start(worker)

    def _show_error(self, msg: str) -> None:
        QtWidgets.QMessageBox.critical(self, "Error", msg)

    def resolve_mismatch(self) -> None:
        files = self.selected_file_paths()
        if not files:
            self.statusBar().showMessage("No files selected")
            return

        self.resolveBtn.setEnabled(False)
        self.statusBar().showMessage("Resolving (merge & sync)...")

        keep_backup = self.keepBackup.isChecked()

        def _work(paths: list[str]) -> TagMutationResult:
            return self.tag_mutations.resolve_mismatches(paths, keep_backup=keep_backup)

        token = self._selection_token
        worker = Worker(_work, files)

        def _ok(res: TagMutationResult) -> None:
            if token == self._selection_token:
                self._keywords_cache.update(res.updated_states)
                self._apply_filter_visibility_changes(res.emptiness_by_path)
                self.statusBar().showMessage(f"Resolved {res.changed_count} file(s)")
                self.on_selection_changed()

        def _err(msg: str) -> None:
            if token == self._selection_token:
                self.statusBar().showMessage("Error")
                self._show_error(msg)
                # Re-enable if still mismatched.
                sel = self.selected_file_paths()
                if sel:
                    st = self._keywords_cache.get(sel[0])
                    self.resolveBtn.setEnabled(bool(st and st.mismatch))

        worker.signals.finished.connect(_ok)
        worker.signals.error.connect(_err)
        self.pool.start(worker)

    def copy_exif_date_to_xmp(self) -> None:
        files = self.selected_file_paths()
        if not files:
            self.statusBar().showMessage("No files selected")
            return
        self.statusBar().showMessage("Copying EXIF date → XMP...")
        keep_backup = self.keepBackup.isChecked()

        worker = Worker(self.exif.copy_exif_date_to_xmp, files, keep_backup)

        def _ok(_: object) -> None:
            self.statusBar().showMessage("Date copied to XMP")

        def _err(msg: str) -> None:
            self.statusBar().showMessage("Error")
            self._show_error(msg)

        worker.signals.finished.connect(_ok)
        worker.signals.error.connect(_err)
        self.pool.start(worker)


def main() -> int:
    app = QtWidgets.QApplication(sys.argv)
    w = MainWindow()
    app.installEventFilter(w)
    w.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
