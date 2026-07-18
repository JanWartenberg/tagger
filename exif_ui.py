import sys
from pathlib import Path
from typing import Callable

from PyQt6 import QtCore, QtGui, QtWidgets

from actions import ActionSpec, KeyRoute, build_action_specs
from exif_tool import ExifTool, ExifToolError, KeywordState
from indexing import IndexSyncResult, PhotoIndex, resolve_index_root
from services.tag_mutation import TagMutationResult, TagMutationService
from storage import add_recent_tag, load_config, load_recent_tags, save_config
from utils import SUPPORTED_EXTS, dedupe_casefold, extract_image_paths_from_urls, normalize_path


DEFAULT_INDEX_ROOT = Path(r"D:\Fotos")


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
        self.setWindowTitle("TAGGER: Tool Annotator, Grouping Guiding EXIF Records")
        self.setAcceptDrops(True)

        self.exif = ExifTool()
        self.tag_mutations = TagMutationService(self.exif)
        self.pool = QtCore.QThreadPool.globalInstance()
        self._mutation_queue: list[tuple[Callable[[], TagMutationResult], str | None]] = []
        self._mutation_inflight = False
        self._keywords_cache: dict[str, KeywordState] = {}
        self._folder_tag_cache: dict[tuple[str, bool], set[str]] = {}
        self._folder_scans_inflight: set[tuple[str, bool]] = set()
        self._index_root: str | None = None
        self._index_sync_inflight: set[str] = set()
        self._selection_token = 0
        self._filter_token = 0
        self._filter_queue: list[list[str]] = []
        self._filter_map: dict[str, QtWidgets.QListWidgetItem] = {}
        self._filter_shown = 0
        self._filter_total = 0
        self._filter_processed = 0
        self._filter_first_chunk = True
        self._filter_switched = False
        # Tagged files stay visible while selected, plus for one navigation step
        # afterwards, so their keywords can be copied to the next image.
        self._filter_preserved: set[str] = set()
        self._filter_previous_selection: set[str] = set()

        self._config = load_config()

        self.files = FileListWidget()
        self.files.filesDropped.connect(self.add_files)
        self.files.itemSelectionChanged.connect(self.on_selection_changed)
        self.files.setToolTip("Focus: f / Alt+1 / Ctrl+W H · Navigate: j/k, gg/G · Copy all tags: Ctrl+C / Space y · Paste: Ctrl+V / Space p")

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

        self.keywordsList = QtWidgets.QListWidget()
        self.keywordsList.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.keywordsList.setToolTip("Focus: l / Alt+3 / Ctrl+W L · Insert: i · Yank: Ctrl+C · Paste: Ctrl+V")

        self.addEdit = QtWidgets.QLineEdit()
        self.addEdit.setPlaceholderText("Add keyword...")
        self.addEdit.returnPressed.connect(self.add_keyword_from_input)
        self.addEdit.setToolTip("Insert: i · Add: Ctrl+Enter")
        self.addBtn = QtWidgets.QPushButton("Add")
        self.addBtn.clicked.connect(self.add_keyword_from_input)
        self.addBtn.setToolTip("Add keyword to selected file(s) (Ctrl+Enter)")
        self.removeBtn = QtWidgets.QPushButton("Remove selected")
        self.removeBtn.clicked.connect(self.remove_selected_keywords)
        self.removeBtn.setToolTip("Remove selected tags from image (Del/Backspace/dd)")

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
        self.knownList = QtWidgets.QListWidget()
        self.knownList.itemActivated.connect(self.add_keyword_from_known)
        self.knownList.itemDoubleClicked.connect(self.add_keyword_from_known)
        self.knownList.setToolTip("Focus: t / Alt+2 / Ctrl+W J · Navigate: j/k, n/N")

        self.recursiveScan = QtWidgets.QCheckBox("Recursive scan")
        self.recursiveScan.setToolTip("Include subfolders when building tag repo")
        self.recursiveScan.setChecked(False)
        self.recursiveScan.toggled.connect(self.force_refresh_known_tags)

        self.onlyUntagged = QtWidgets.QCheckBox("Only IPTC-empty")
        self.onlyUntagged.setToolTip("Show only files without IPTC keywords (Ctrl+Shift+E)")
        self.onlyUntagged.toggled.connect(
            lambda _checked: self.apply_iptc_filter_async(reset_preserved=True)
        )
        self.dbSearchEdit = QtWidgets.QLineEdit()
        self.dbSearchEdit.setPlaceholderText("Search DB tags/date...")
        self.dbSearchEdit.setToolTip("Reverse search in the SQLite index: tag:foo or date:2024")
        self.dbSearchEdit.returnPressed.connect(self.apply_db_search)
        self.dbSearchBtn = QtWidgets.QPushButton("Search")
        self.dbSearchBtn.clicked.connect(self.apply_db_search)
        self.dbSearchClearBtn = QtWidgets.QPushButton("Clear")
        self.dbSearchClearBtn.clicked.connect(self.clear_db_search)
        self.filterInfoLabel = QtWidgets.QLabel("")
        self.filterInfoLabel.setToolTip("Filter result count")

        self.addFolderBtn = QtWidgets.QPushButton("Add folder")
        self.addFolderBtn.setToolTip("Add all JPG/JPEG files from a folder (Ctrl+O)")
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
        filesSearchRowW = QtWidgets.QWidget()
        filesSearchRow = QtWidgets.QHBoxLayout(filesSearchRowW)
        filesSearchRow.setContentsMargins(0, 0, 0, 0)
        filesSearchRow.addWidget(self.dbSearchEdit, 1)
        filesSearchRow.addWidget(self.dbSearchBtn)
        filesSearchRow.addWidget(self.dbSearchClearBtn)
        filesLayout.addWidget(filesSearchRowW)
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
        self._vim_repeated_key_pending: dict[tuple[str, int], int] = {}
        self._vim_space_pending: int | None = None
        self._vim_visual_keywords = False
        self._vim_visual_anchor = 0
        self._yanked_tags: list[str] = []
        self._last_left_pane: QtWidgets.QListWidget = self.files
        self._actions_by_id: dict[str, ActionSpec] = {}
        self._commands_by_name: dict[str, ActionSpec] = {}
        self._listed_actions: list[ActionSpec] = []
        self._action_handlers: dict[str, Callable[[], None]] = {}
        self._widget_refs: dict[str, QtCore.QObject] = {}
        self._init_actions()

    def _init_actions(self) -> None:
        specs = build_action_specs()
        self._actions_by_id = {spec.id: spec for spec in specs}
        self._listed_actions = [spec for spec in specs if spec.command is not None and spec.show_in_help]
        self._widget_refs = self._build_widget_refs()
        self._action_handlers = self._build_action_handlers()
        self._commands_by_name = {}
        self._install_shortcuts_from_actions()
        self._index_commands_from_actions()

    def _build_widget_refs(self) -> dict[str, QtCore.QObject]:
        return {
            "window": self,
            "files": self.files,
            "keywordsList": self.keywordsList,
            "knownList": self.knownList,
            "addEdit": self.addEdit,
            "knownFilter": self.knownFilter,
            "cmdLine": self.cmdLine,
        }

    def _index_root_for_paths(self, paths: list[str]) -> str | None:
        root = resolve_index_root(paths, preferred_root=DEFAULT_INDEX_ROOT)
        return str(root) if root is not None else self._index_root

    def _photo_index(self, root: str | None) -> PhotoIndex | None:
        if not root:
            return None
        return PhotoIndex(root)

    def _schedule_index_sync(self, root: str | None) -> None:
        if not root:
            return
        root = normalize_path(root)
        index = PhotoIndex(root)
        if index.is_initialized():
            self._index_root = root
            return
        if root in self._index_sync_inflight:
            return
        self._index_sync_inflight.add(root)
        self._index_root = root
        self.statusBar().showMessage("Indexing photos...")

        worker = Worker(self._run_index_sync, root)

        def _ok(result: IndexSyncResult) -> None:
            self._index_sync_inflight.discard(root)
            if self._index_root == root:
                self.statusBar().showMessage(
                    f"Index ready: {result.updated_count} updated, {result.deleted_count} removed"
                )
                self.refresh_known_tags()

        def _err(msg: str) -> None:
            self._index_sync_inflight.discard(root)
            if self._index_root == root:
                self.statusBar().showMessage("Indexing failed")
                self._show_error(msg)

        worker.signals.finished.connect(_ok)
        worker.signals.error.connect(_err)
        self.pool.start(worker)

    def _run_index_sync(self, root: str) -> IndexSyncResult:
        index = PhotoIndex(root)
        return index.sync_root(self.exif)

    def _update_index_states(self, states: dict[str, KeywordState]) -> None:
        if not states:
            return
        root = self._index_root_for_paths(list(states.keys()))
        if not root:
            return
        index = self._photo_index(root)
        if index is None:
            return
        index.update_states(states)

    def _index_missing_paths(self, root: str, paths: list[str]) -> None:
        index = PhotoIndex(root)
        existing = index.has_photos(paths)
        missing = [normalize_path(p) for p in paths if normalize_path(p) not in existing]
        if not missing:
            return

        worker = Worker(self.exif.read_keywords_many, missing)

        def _ok(states: dict[str, KeywordState]) -> None:
            if states:
                index.update_states(states)
                self._keywords_cache.update(states)
                self.refresh_known_tags()

        def _err(msg: str) -> None:
            self._show_error(msg)

        worker.signals.finished.connect(_ok)
        worker.signals.error.connect(_err)
        self.pool.start(worker)

    def _build_action_handlers(self) -> dict[str, Callable[[], None]]:
        return {
            "_cmd_list_commands": lambda: self._cmd_list_commands(),
            "_cmd_quit": lambda: self._cmd_quit(),
            "add_folder_dialog": self.add_folder_dialog,
            "force_refresh_known_tags": self.force_refresh_known_tags,
            "resolve_mismatch": self.resolve_mismatch,
            "add_keyword_from_input": self.add_keyword_from_input,
            "remove_selected_keywords": self.remove_selected_keywords,
            "_focus_known_filter_select_all": self._focus_known_filter_select_all,
            "_focus_add_edit_select_all": self._focus_add_edit_select_all,
            "_focus_pane_files": self._focus_pane_files,
            "_focus_pane_known": self._focus_pane_known,
            "_focus_pane_keywords": self._focus_pane_keywords,
            "_toggle_keep_backup": self._toggle_keep_backup,
            "_toggle_only_iptc_empty": self._toggle_only_iptc_empty,
            "_focus_next_pane": self._focus_next_pane,
            "_focus_pane_left": self._focus_pane_left,
            "_focus_pane_right": self._focus_pane_right,
            "_focus_pane_down": self._focus_pane_down,
            "_focus_pane_up": self._focus_pane_up,
            "_action_list_down": self._action_list_down,
            "_action_list_up": self._action_list_up,
            "_action_list_top": self._action_list_top,
            "_action_list_bottom": self._action_list_bottom,
            "_action_known_next": self._action_known_next,
            "_action_known_prev": self._action_known_prev,
            "_toggle_visual_keywords": self._toggle_visual_keywords,
            "_yank_selected_tags": self._yank_selected_tags,
            "_yank_current_file_tags": self._yank_current_file_tags,
            "_paste_yanked_tags": self._paste_yanked_tags,
            "_escape_action": self._escape_action,
            "_open_command_line": self._open_command_line,
            "_tab_complete_command_line": self._tab_complete_command_line,
            "_tab_complete_add_edit": self._tab_complete_add_edit,
        }

    def _install_shortcuts_from_actions(self) -> None:
        self._shortcuts = []
        for spec in self._actions_by_id.values():
            for binding in spec.shortcuts:
                widget = self._widget_refs.get(binding.widget_ref)
                if widget is None:
                    continue
                shortcut = QtGui.QShortcut(QtGui.QKeySequence(binding.sequence), widget)
                shortcut.setContext(binding.context)
                shortcut.activated.connect(lambda action_id=spec.id: self._dispatch_action(action_id))
                self._shortcuts.append(shortcut)

    def _index_commands_from_actions(self) -> None:
        for spec in self._listed_actions:
            command = spec.command
            if command is None:
                continue
            self._commands_by_name[command.name] = spec
            for alias in command.aliases:
                self._commands_by_name[alias] = spec

    def _dispatch_action(self, action_id: str) -> None:
        spec = self._actions_by_id.get(action_id)
        if spec is None:
            raise RuntimeError(f"Unknown action: {action_id}")
        handler = self._action_handlers.get(spec.handler_name)
        if handler is None:
            raise RuntimeError(f"Missing handler for action: {spec.id} ({spec.handler_name})")
        handler()

    def _dispatch_command(self, name: str, args: list[str]) -> None:
        spec = self._commands_by_name.get(name)
        if spec is None:
            self.statusBar().showMessage(f"Unknown command: {name}")
            return
        try:
            self._dispatch_action(spec.id)
        except Exception as e:
            self._show_error(str(e))

    def _format_key_route_label(self, route: KeyRoute) -> str:
        if route.kind == "sequence":
            if len(route.sequence) == 2 and route.sequence[0] == route.sequence[1]:
                return "".join(route.sequence)
            return "+".join(route.sequence)
        return route.sequence[0]

    def _action_help_labels(self, spec: ActionSpec) -> list[str]:
        labels: list[str] = []
        command = spec.command
        if command is not None and spec.id in {"listcommands", "quit"}:
            labels.append(f":{command.name}")
            labels.extend(f":{alias}" for alias in command.aliases)
        labels.extend(binding.sequence for binding in spec.shortcuts if binding.show_in_help)
        labels.extend(self._format_key_route_label(route) for route in spec.key_routes if route.show_in_help)
        labels.extend(trigger.label for trigger in spec.native_triggers)
        return labels

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
        if et == QtCore.QEvent.Type.ShortcutOverride and isinstance(event, QtGui.QKeyEvent):
            if self._handle_shortcut_override(event):
                return True
        if et == QtCore.QEvent.Type.KeyPress and isinstance(event, QtGui.QKeyEvent):
            if self._handle_key_routes(obj, event):
                return True
        if et == QtCore.QEvent.Type.FocusIn:
            if obj in (self.files, self.knownList):
                self._last_left_pane = obj
        return super().eventFilter(obj, event)

    def _list_from_obj(self, obj: QtCore.QObject | None) -> QtWidgets.QListWidget | None:
        cur = obj
        while cur is not None:
            if cur in (self.files, self.knownList, self.keywordsList):
                return cur
            try:
                cur = cur.parent()
            except Exception:
                break
        return None

    def _resolve_current_list_widget(self, obj: QtCore.QObject | None = None) -> QtWidgets.QListWidget | None:
        return self._list_from_obj(obj) or self._list_from_obj(self.focusWidget())

    def _event_token(self, event: QtGui.QKeyEvent) -> str | None:
        if (
            event.key() == QtCore.Qt.Key.Key_C
            and event.modifiers() == QtCore.Qt.KeyboardModifier.ControlModifier
        ):
            return "Ctrl+C"
        if event.key() == QtCore.Qt.Key.Key_Tab:
            return "Tab"
        if event.key() == QtCore.Qt.Key.Key_Space:
            return "Space"
        if event.text() == ":":
            return ":"
        if (
            event.key() == QtCore.Qt.Key.Key_G
            and event.modifiers() & QtCore.Qt.KeyboardModifier.ShiftModifier
        ):
            return "G"
        text = event.text()
        if text:
            return text
        key_map = {
            QtCore.Qt.Key.Key_I: "i",
            QtCore.Qt.Key.Key_T: "t",
            QtCore.Qt.Key.Key_F: "f",
            QtCore.Qt.Key.Key_G: "g",
            QtCore.Qt.Key.Key_J: "j",
            QtCore.Qt.Key.Key_K: "k",
            QtCore.Qt.Key.Key_Y: "y",
            QtCore.Qt.Key.Key_P: "p",
        }
        return key_map.get(event.key())

    def _scope_matches(
        self,
        route: KeyRoute,
        obj: QtCore.QObject | None,
        list_widget: QtWidgets.QListWidget | None,
    ) -> bool:
        if route.scope == "global_non_input":
            return True
        if route.scope == "list_widgets":
            return list_widget is not None
        if route.scope == "widget_exact":
            current = self._list_from_obj(obj) or obj
            if current is None:
                return False
            for ref in route.widget_refs:
                target = self._widget_refs.get(ref)
                if target is None:
                    continue
                if current is target:
                    return True
            return False
        return False

    def _find_matching_single_route(
        self,
        token: str,
        scope: str,
        obj: QtCore.QObject | None,
        list_widget: QtWidgets.QListWidget | None,
    ) -> ActionSpec | None:
        for spec in self._actions_by_id.values():
            for route in spec.key_routes:
                if route.scope != scope or route.kind not in ("single", "widget_specific"):
                    continue
                if route.sequence != (token,):
                    continue
                if self._scope_matches(route, obj, list_widget):
                    return spec
        return None

    def _handle_shortcut_override(self, event: QtGui.QKeyEvent) -> bool:
        if isinstance(self.focusWidget(), QtWidgets.QLineEdit):
            return False
        if not self._mods_ok(event.modifiers()):
            return False
        token = self._event_token(event)
        if token is None:
            return False
        list_widget = self._resolve_current_list_widget()
        for scope in ("global_non_input", "list_widgets"):
            if self._find_matching_single_route(token, scope, self.focusWidget(), list_widget) is not None:
                event.accept()
                return True
        return False

    def _handle_prefix_route(
        self,
        route: KeyRoute,
        action_id: str,
        token: str,
        obj: QtCore.QObject | None,
        list_widget: QtWidgets.QListWidget | None,
    ) -> bool:
        if len(route.sequence) != 2:
            return False
        if not self._scope_matches(route, obj, list_widget):
            return False

        prefix, suffix = route.sequence
        timeout_ms = route.timeout_ms or 600
        now = int(QtCore.QDateTime.currentMSecsSinceEpoch())

        if prefix == suffix:
            if list_widget is None:
                return False
            if route.widget_refs:
                allowed_widgets = {
                    self._widget_refs[ref]
                    for ref in route.widget_refs
                    if ref in self._widget_refs
                }
                if list_widget not in allowed_widgets:
                    return False
            key = (prefix, id(list_widget))
            last = self._vim_repeated_key_pending.get(key)
            if token == prefix and last is not None and (now - last) <= timeout_ms:
                self._vim_repeated_key_pending.pop(key, None)
                self._dispatch_action(action_id)
                return True
            if token == prefix:
                self._vim_repeated_key_pending[key] = now
                return True
            if last is not None:
                self._vim_repeated_key_pending.pop(key, None)
            return False

        if prefix == "Space":
            if token == prefix:
                self._vim_space_pending = now
                return True
            if token == suffix and self._vim_space_pending is not None:
                if route.widget_refs and list_widget is not None:
                    allowed_widgets = {
                        self._widget_refs[ref]
                        for ref in route.widget_refs
                        if ref in self._widget_refs
                    }
                    if list_widget not in allowed_widgets:
                        return False
                if (now - self._vim_space_pending) <= timeout_ms:
                    self._vim_space_pending = None
                    self._dispatch_action(action_id)
                    return True
                self._vim_space_pending = None
                return False
            if self._vim_space_pending is not None and (now - self._vim_space_pending) > timeout_ms:
                self._vim_space_pending = None
            return False

        return False

    def _handle_key_routes(self, obj: QtCore.QObject, event: QtGui.QKeyEvent) -> bool:
        token = self._event_token(event)
        if token is None:
            return False

        focus = self.focusWidget()
        list_widget = self._resolve_current_list_widget(obj)

        if not isinstance(focus, QtWidgets.QLineEdit) and self._mods_ok(event.modifiers()):
            for scope in ("global_non_input", "list_widgets"):
                match = self._find_matching_single_route(token, scope, obj, list_widget)
                if match is not None:
                    self._dispatch_action(match.id)
                    return True
                for spec in self._actions_by_id.values():
                    for route in spec.key_routes:
                        if route.scope == scope and route.kind == "sequence":
                            if self._handle_prefix_route(route, spec.id, token, obj, list_widget):
                                return True

        widget_match = self._find_matching_single_route(token, "widget_exact", obj, list_widget)
        if widget_match is not None:
            self._dispatch_action(widget_match.id)
            return True

        for spec in self._actions_by_id.values():
            for route in spec.key_routes:
                if route.scope == "widget_exact" and route.kind == "sequence":
                    if self._handle_prefix_route(route, spec.id, token, obj, list_widget):
                        return True

        return False

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
        self._hide_tag_matches()
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
        self._dispatch_command(name, args)

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
        out = [name for name in self._commands_by_name if name.startswith(prefix)]
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

    def _cmd_list_commands(self, _args: list[str] | None = None) -> None:
        lines: list[str] = []
        for spec in sorted(self._listed_actions, key=lambda action: action.command.name if action.command else action.id):
            command = spec.command
            if command is None:
                continue
            alias = f" (aliases: {', '.join(command.aliases)})" if command.aliases else ""
            labels = self._action_help_labels(spec)
            shorts = f" [{', '.join(labels)}]" if labels else ""
            lines.append(f"{command.name}{alias} — {spec.description}{shorts}")
        text = "\n".join(lines) if lines else "(no commands)"
        QtWidgets.QMessageBox.information(self, "Commands", text)

    def _cmd_quit(self, _args: list[str] | None = None) -> None:
        self.close()

    def _focus_pane_files(self) -> None:
        self._focus_pane(self.files)

    def _focus_pane_known(self) -> None:
        self._focus_pane(self.knownList)

    def _focus_pane_keywords(self) -> None:
        self._focus_pane(self.keywordsList)

    def _focus_pane_left(self) -> None:
        self._focus_pane_by_direction("left")

    def _focus_pane_right(self) -> None:
        self._focus_pane_by_direction("right")

    def _focus_pane_down(self) -> None:
        self._focus_pane_by_direction("down")

    def _focus_pane_up(self) -> None:
        self._focus_pane_by_direction("up")

    def _action_list_down(self) -> None:
        lst = self._resolve_current_list_widget()
        if lst is not None:
            self._move_list_selection(lst, +1)

    def _action_list_up(self) -> None:
        lst = self._resolve_current_list_widget()
        if lst is not None:
            self._move_list_selection(lst, -1)

    def _action_list_top(self) -> None:
        lst = self._resolve_current_list_widget()
        if lst is not None:
            self._go_list_edge(lst, to_end=False)

    def _action_list_bottom(self) -> None:
        lst = self._resolve_current_list_widget()
        if lst is not None:
            self._go_list_edge(lst, to_end=True)

    def _action_known_next(self) -> None:
        self._move_list_selection(self.knownList, +1)

    def _action_known_prev(self) -> None:
        self._move_list_selection(self.knownList, -1)

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

    def _yank_current_file_tags(self) -> None:
        files = self.selected_file_paths()
        if not files:
            self.statusBar().showMessage("No file selected")
            return
        state = self._keywords_cache.get(files[0])
        if state is None:
            self.statusBar().showMessage("Tags are still loading")
            return
        self._yanked_tags = state.merged
        if not self._yanked_tags:
            self.statusBar().showMessage("Current file has no tags")
            return
        self.statusBar().showMessage(f"Yanked all {len(self._yanked_tags)} tag(s)")

    def _paste_yanked_tags(self) -> None:
        if not self._yanked_tags:
            self.statusBar().showMessage("Yank tags first")
            return
        files = self.selected_file_paths()
        if not files:
            self.statusBar().showMessage("No files selected")
            return
        target = files[0]
        optimistic = self._optimistic_mutation(
            [target],
            lambda st: st.merged + self._yanked_tags,
        )
        if optimistic.updated_states:
            self._apply_tag_mutation_result(optimistic)
        self.statusBar().showMessage(f"Queued paste ({len(self._yanked_tags)} tag(s))")
        self._enqueue_tag_mutation(
            lambda: self.tag_mutations.add_tags(
                [target],
                self._yanked_tags,
                keep_backup=self.keepBackup.isChecked(),
                load_state=self._ensure_loaded,
            ),
            f"Pasted {len(self._yanked_tags)} tag(s)",
        )

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
        root = self._index_root_for_paths(self.all_file_paths())
        if root:
            self._index_root = root
            index = PhotoIndex(root)
            if index.is_initialized():
                self._index_missing_paths(root, paths)
            else:
                self._schedule_index_sync(root)

    def _reset_files_pane_for_reload(self) -> None:
        # Cancel in-flight async work that would render stale UI.
        self._selection_token += 1
        self._preview_token += 1
        self._filter_token += 1
        self._filter_queue = []

        # Reset caches tied to previous file lists.
        self._keywords_cache = {}
        self._filter_map = {}
        self._filter_preserved = set()
        self._filter_previous_selection = set()
        self._folder_tag_cache = {}
        self._folder_scans_inflight = set()
        self._index_root = None

        # Clear list + selection without spamming selection-changed handlers mid-reset.
        self.files.blockSignals(True)
        try:
            self.files.clearSelection()
            self.files.setCurrentRow(-1)
            self.files.clear()
        finally:
            self.files.blockSignals(False)

        self.filterInfoLabel.setText("")
        self.on_selection_changed()

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

        # Ctrl+O is treated as a (re)load: wipe the pane + right side first.
        self._reset_files_pane_for_reload()

        p = Path(folder)
        paths = [str(x) for x in p.rglob("*") if x.is_file() and x.suffix.lower() in SUPPORTED_EXTS]
        if paths:
            self.add_files(paths)
        self._set_last_folder(folder)
        root = self._index_root_for_paths(paths or [folder])
        if root:
            self._index_root = root
        self._schedule_index_sync(root)
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
            self._update_index_states({current: st})
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
        changed = False

        hidden_selected = [it for it in self.files.selectedItems() if it.isHidden()]
        for it in hidden_selected:
            it.setSelected(False)
            changed = True

        current = self.files.currentItem()
        if current is not None and current.isHidden():
            self.files.setCurrentRow(-1)
            changed = True

        selected_visible = [it for it in self.files.selectedItems() if not it.isHidden()]
        if selected_visible:
            target = current if current in selected_visible else selected_visible[0]
            if target is not current:
                changed = True
            self.files.setCurrentItem(target)
            self.files.scrollToItem(target)
            if changed:
                self.files.setFocus()
                QtCore.QTimer.singleShot(0, self.on_selection_changed)
            return
        for i in range(self.files.count()):
            it = self.files.item(i)
            if it is not None and not it.isHidden():
                self.files.clearSelection()
                it.setSelected(True)
                self.files.setCurrentItem(it)
                self.files.scrollToItem(it)
                self.files.setFocus()
                changed = True
                if changed:
                    QtCore.QTimer.singleShot(0, self.on_selection_changed)
                return

        # No visible items left (e.g. empty-filter yields 0): hard-reset selection/current.
        self.files.clearSelection()
        self.files.setCurrentRow(-1)
        if changed:
            QtCore.QTimer.singleShot(0, self.on_selection_changed)

    def apply_iptc_filter_async(self, reset_preserved: bool = False) -> None:
        self._filter_token += 1
        token = self._filter_token
        if reset_preserved:
            self._filter_preserved = set()
            self._filter_previous_selection = set()
        if not self.onlyUntagged.isChecked():
            self._filter_previous_selection = set()
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
        self._update_index_states(result.updated_states)
        self._refresh_current_keywords_view_from_cache()
        self._apply_filter_visibility_changes(result.emptiness_by_path)

    def _current_keywords_from_ui(self) -> list[str]:
        items = [self.keywordsList.item(i) for i in range(self.keywordsList.count())]
        return [it.text().strip() for it in items if it is not None and it.text().strip()]

    def _optimistic_mutation(
        self,
        files: list[str],
        transform: Callable[[KeywordState], list[str]],
    ) -> TagMutationResult:
        updated_states: dict[str, KeywordState] = {}
        emptiness_by_path: dict[str, bool] = {}
        selected = self.selected_file_paths()
        current = normalize_path(selected[0]) if selected else None

        for path in files:
            st = self._keywords_cache.get(path)
            if st is None and current and normalize_path(path) == current:
                kws = self._current_keywords_from_ui()
                st = KeywordState(kws, kws)
            if st is None:
                continue
            keywords = transform(st)
            keywords = dedupe_casefold([k.strip() for k in keywords if k.strip()])
            keywords.sort(key=lambda value: value.casefold())
            updated_states[path] = KeywordState(
                keywords,
                keywords,
                st.date_original,
                st.date_create,
                st.date_xmp_create,
                st.date_digitized,
            )
            emptiness_by_path[path] = len(keywords) == 0

        return TagMutationResult(
            updated_states=updated_states,
            emptiness_by_path=emptiness_by_path,
            processed_count=len(files),
            changed_count=len(updated_states),
        )

    def _enqueue_tag_mutation(
        self,
        fn: Callable[[], TagMutationResult],
        status: str | None = None,
    ) -> None:
        self._mutation_queue.append((fn, status))
        self._process_tag_mutation_queue()

    def _process_tag_mutation_queue(self) -> None:
        if self._mutation_inflight or not self._mutation_queue:
            return
        self._mutation_inflight = True
        fn, status = self._mutation_queue.pop(0)
        worker = Worker(fn)

        def _ok(result: TagMutationResult) -> None:
            self._mutation_inflight = False
            self._apply_tag_mutation_result(result)
            if status:
                self.statusBar().showMessage(status)
            self._process_tag_mutation_queue()

        def _err(msg: str) -> None:
            self._mutation_inflight = False
            self.statusBar().showMessage("Error")
            self._show_error(msg)
            self._process_tag_mutation_queue()

        worker.signals.finished.connect(_ok)
        worker.signals.error.connect(_err)
        self.pool.start(worker)

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

    def clear_db_search(self) -> None:
        self.dbSearchEdit.clear()
        self._apply_db_search_results(None)
        self.statusBar().showMessage("DB search cleared")
        self.on_selection_changed()

    def apply_db_search(self) -> None:
        query = (self.dbSearchEdit.text() or "").strip()
        if not query:
            self.clear_db_search()
            return
        if self.onlyUntagged.isChecked():
            self.onlyUntagged.setChecked(False)
        root = self._index_root_for_paths(self.all_file_paths())
        if not root:
            self.statusBar().showMessage("No index root available")
            return
        try:
            matches = set(PhotoIndex(root).search_photos(query))
        except Exception as e:
            self._show_error(str(e))
            return
        self._apply_db_search_results(matches)
        self.statusBar().showMessage(f"DB search: {len(matches)} match(es)")

    def _apply_db_search_results(self, matches: set[str] | None) -> None:
        def _do() -> None:
            first_visible_row: int | None = None
            for i in range(self.files.count()):
                it = self.files.item(i)
                if it is None:
                    continue
                show = True if matches is None else normalize_path(it.text()) in matches
                it.setHidden(not show)
                if show and first_visible_row is None:
                    first_visible_row = i

            current = self.files.currentItem()
            current_visible = current is not None and not current.isHidden()
            if first_visible_row is not None and not current_visible:
                self.files.setCurrentRow(first_visible_row)

        self._preserve_files_scroll(_do)
        self._ensure_files_focus_visible()

    def _sync_filter_preserved_selection(self, selected_paths: list[str]) -> None:
        if not self.onlyUntagged.isChecked():
            self._filter_previous_selection = set()
            return

        selected = {normalize_path(p) for p in selected_paths}
        # Keep a just-tagged image visible when moving to the next result. This
        # provides one step back for copying its tags without turning the filter
        # into a growing list of already-tagged files.
        allowed = selected | self._filter_previous_selection
        released = self._filter_preserved - allowed
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
        self._filter_preserved &= allowed
        self._filter_previous_selection = selected

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
        optimistic = self._optimistic_mutation(files, lambda st: st.merged + [tag])
        if optimistic.updated_states:
            self._apply_tag_mutation_result(optimistic)
        add_recent_tag(tag)
        self.statusBar().showMessage(f"Queued add '{tag}' to {len(files)} file(s)")
        self._enqueue_tag_mutation(
            lambda: self.tag_mutations.add_tag(
                files,
                tag,
                keep_backup=self.keepBackup.isChecked(),
                load_state=self._ensure_loaded,
            ),
            f"Added '{tag}' to {len(files)} file(s)",
        )

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
        optimistic = self._optimistic_mutation(
            files,
            lambda st: [tag for tag in st.merged if tag.casefold() not in remove],
        )
        if optimistic.updated_states:
            self._apply_tag_mutation_result(optimistic)
        self.statusBar().showMessage(f"Queued remove {len(remove)} tag(s) from {len(files)} file(s)")
        self._enqueue_tag_mutation(
            lambda: self.tag_mutations.remove_tags(
                files,
                remove,
                keep_backup=self.keepBackup.isChecked(),
                load_state=self._ensure_loaded,
            ),
            f"Removed {len(remove)} tag(s) from {len(files)} file(s)",
        )

    def force_refresh_known_tags(self) -> None:
        self.refresh_known_tags()

    def refresh_known_tags(self) -> None:
        filter_text = (self.knownFilter.text() or "").strip().casefold()
        recent = load_recent_tags()

        folder_tags: set[str] = set()
        paths = self.selected_file_paths() or self.all_file_paths()
        if paths:
            root = self._index_root_for_paths(paths)
            if root:
                self._index_root = root
                try:
                    folder_tags = PhotoIndex(root).load_tags_for_root()
                except Exception:
                    folder_tags = set()

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
        self._schedule_index_sync(folder)

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
                self._update_index_states(res.updated_states)
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
