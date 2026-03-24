import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from PyQt6 import QtCore, QtGui, QtWidgets


SUPPORTED_EXTS = {".jpg", ".jpeg"}

APP_DIR_NAME = "exif_ui"
LEGACY_APP_DIR_NAME = "exif_keywords_mvp"


def dedupe_casefold(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for s in items:
        s2 = s.strip()
        if not s2:
            continue
        key = s2.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(s2)
    return out


def extract_image_paths_from_urls(urls: list[QtCore.QUrl]) -> list[str]:
    paths: list[str] = []
    for u in urls:
        if not u.isLocalFile():
            continue
        p = Path(u.toLocalFile())
        if p.is_dir():
            for child in p.rglob("*"):
                if child.is_file() and child.suffix.lower() in SUPPORTED_EXTS:
                    paths.append(str(child))
        else:
            if p.suffix.lower() in SUPPORTED_EXTS:
                paths.append(str(p))
    return paths


def _app_data_dir() -> Path:
    base = os.getenv("APPDATA") or str(Path.home())
    d = Path(base) / APP_DIR_NAME
    d.mkdir(parents=True, exist_ok=True)
    return d


def _recent_tags_path() -> Path:
    return _app_data_dir() / "recent_tags.json"


def _legacy_recent_tags_path() -> Path:
    base = os.getenv("APPDATA") or str(Path.home())
    return Path(base) / LEGACY_APP_DIR_NAME / "recent_tags.json"


def load_recent_tags() -> list[str]:
    p = _recent_tags_path()
    if not p.exists():
        legacy = _legacy_recent_tags_path()
        if legacy.exists():
            try:
                data = json.loads(legacy.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    tags: list[str] = []
                    for x in data:
                        if isinstance(x, str) and x.strip():
                            tags.append(x.strip())
                    save_recent_tags(tags)
                    return tags[:100]
            except Exception:
                pass
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return []
    if not isinstance(data, list):
        return []
    out: list[str] = []
    for x in data:
        if isinstance(x, str) and x.strip():
            out.append(x.strip())
    return out[:100]


def save_recent_tags(tags: list[str]) -> None:
    p = _recent_tags_path()
    p.write_text(json.dumps(tags[:100], ensure_ascii=True, indent=2), encoding="utf-8")


def add_recent_tag(tag: str) -> None:
    tag = tag.strip()
    if not tag:
        return
    tags = load_recent_tags()
    tags = [t for t in tags if t.lower() != tag.lower()]
    tags.insert(0, tag)
    save_recent_tags(tags)


@dataclass
class KeywordState:
    iptc: list[str]
    xmp: list[str]

    @property
    def iptc_set(self) -> set[str]:
        return {k for k in self.iptc if k.strip()}

    @property
    def xmp_set(self) -> set[str]:
        return {k for k in self.xmp if k.strip()}

    @property
    def merged(self) -> list[str]:
        merged = list(self.iptc_set | self.xmp_set)
        merged = dedupe_casefold(merged)
        merged.sort(key=lambda s: s.casefold())
        return merged

    @property
    def mismatch(self) -> bool:
        return self.iptc_set != self.xmp_set


class ExifToolError(RuntimeError):
    pass


class ExifTool:
    def __init__(self, exe: str = "exiftool"):
        self.exe = exe

    def _run(self, args: list[str]) -> str:
        try:
            p = subprocess.run(
                [self.exe, *args],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
        except FileNotFoundError as e:
            raise ExifToolError(
                "exiftool not found on PATH. Install it and ensure `exiftool -ver` works."
            ) from e
        if p.returncode != 0:
            stderr = (p.stderr or "").strip()
            raise ExifToolError(stderr or f"exiftool failed with exit code {p.returncode}")
        return p.stdout

    def read_keywords(self, file_path: str) -> KeywordState:
        out = self._run(
            ["-q", "-q", "-j", "-G1", "-IPTC:Keywords", "-XMP-dc:Subject", file_path]
        )
        try:
            data = json.loads(out)
        except Exception as e:
            raise ExifToolError("Failed to parse exiftool JSON output") from e
        if not data:
            return KeywordState([], [])

        rec = data[0]
        iptc = rec.get("IPTC:Keywords", [])
        xmp = rec.get("XMP-dc:Subject", [])
        if isinstance(iptc, str):
            iptc = [iptc]
        if isinstance(xmp, str):
            xmp = [xmp]

        def _clean(v: object) -> list[str]:
            if not isinstance(v, list):
                return []
            out2: list[str] = []
            for x in v:
                if isinstance(x, str) and x.strip():
                    out2.append(x.strip())
            return out2

        return KeywordState(_clean(iptc), _clean(xmp))

    def write_keywords(self, file_paths: list[str], keywords: list[str], keep_backup: bool) -> None:
        kws = dedupe_casefold([k.strip() for k in keywords if k.strip()])
        kws.sort(key=lambda s: s.casefold())
        # Clear both lists, then set explicit values (avoid duplicates).
        args: list[str] = []
        if not keep_backup:
            args.append("-overwrite_original")
        args += ["-P", "-IPTC:Keywords=", "-XMP-dc:Subject="]
        for kw in kws:
            args.append(f"-IPTC:Keywords={kw}")
            args.append(f"-XMP-dc:Subject={kw}")
        args += file_paths
        self._run(args)

    def scan_folder_tags(self, folder: str) -> set[str]:
        out = self._run(
            [
                "-q",
                "-q",
                "-j",
                "-G1",
                # Non-recursive by design: only tags from the same folder.
                "-ext",
                "jpg",
                "-ext",
                "jpeg",
                "-IPTC:Keywords",
                "-XMP-dc:Subject",
                folder,
            ]
        )
        try:
            data = json.loads(out)
        except Exception as e:
            raise ExifToolError("Failed to parse exiftool JSON output") from e
        tags: set[str] = set()
        for rec in data:
            iptc = rec.get("IPTC:Keywords", [])
            xmp = rec.get("XMP-dc:Subject", [])
            if isinstance(iptc, str):
                iptc = [iptc]
            if isinstance(xmp, str):
                xmp = [xmp]
            for lst in (iptc, xmp):
                if isinstance(lst, list):
                    for x in lst:
                        if isinstance(x, str) and x.strip():
                            tags.add(x.strip())
        return tags


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
        self.pool = QtCore.QThreadPool.globalInstance()
        self._keywords_cache: dict[str, KeywordState] = {}
        self._folder_tag_cache: dict[str, set[str]] = {}
        self._folder_scans_inflight: set[str] = set()
        self._selection_token = 0

        self.files = FileListWidget()
        self.files.filesDropped.connect(self.add_files)
        self.files.itemSelectionChanged.connect(self.on_selection_changed)

        self.selectedLabel = QtWidgets.QLabel("Drop JPG/JPEG files here")
        self.selectedLabel.setTextInteractionFlags(QtCore.Qt.TextInteractionFlag.TextSelectableByMouse)

        self.previewLabel = QtWidgets.QLabel("No preview")
        self.previewLabel.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.previewLabel.setMinimumHeight(220)
        self.previewLabel.setStyleSheet(
            "QLabel { background: palette(window); color: palette(text); "
            "border: 1px solid palette(mid); border-radius: 8px; }"
        )
        self._preview_token = 0
        self.mismatchLabel = QtWidgets.QLabel("")
        self.mismatchLabel.setStyleSheet("color: #b45309;")
        self.resolveBtn = QtWidgets.QPushButton("Resolve (sync both)")
        self.resolveBtn.setEnabled(False)
        self.resolveBtn.clicked.connect(self.resolve_mismatch)
        self.resolveBtn.setToolTip("Resolve IPTC/XMP mismatch (Ctrl+R)")
        self.resolveBtn.setShortcut(QtGui.QKeySequence("Ctrl+R"))

        self.keywordsList = QtWidgets.QListWidget()
        self.keywordsList.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection)

        self.addEdit = QtWidgets.QLineEdit()
        self.addEdit.setPlaceholderText("Add keyword...")
        self.addEdit.returnPressed.connect(self.add_keyword_from_input)
        self.addBtn = QtWidgets.QPushButton("Add")
        self.addBtn.clicked.connect(self.add_keyword_from_input)
        self.addBtn.setToolTip("Add keyword to selected file(s) (Ctrl+Enter)")
        self.removeBtn = QtWidgets.QPushButton("Remove selected")
        self.removeBtn.clicked.connect(self.remove_selected_keywords)
        self.removeBtn.setToolTip("Remove selected tags from image (Del)")
        self.removeBtn.setShortcut(QtGui.QKeySequence("Del"))

        self.keepBackup = QtWidgets.QCheckBox("Keep *_original backups (exiftool default)")
        self.keepBackup.setChecked(True)
        self.keepBackup.setToolTip("If enabled, exiftool keeps *_original backups")

        self.knownFilter = QtWidgets.QLineEdit()
        self.knownFilter.setPlaceholderText("Filter known tags...")
        self.knownFilter.textChanged.connect(self.refresh_known_tags)
        self.knownRefreshBtn = QtWidgets.QPushButton("Refresh")
        self.knownRefreshBtn.setFixedWidth(80)
        self.knownRefreshBtn.clicked.connect(self.force_refresh_known_tags)
        self.knownRefreshBtn.setToolTip("Refresh tag repo (F5)")
        self.knownRefreshBtn.setShortcut(QtGui.QKeySequence("F5"))
        self.knownList = QtWidgets.QListWidget()
        self.knownList.itemActivated.connect(self.add_keyword_from_known)
        self.knownList.itemDoubleClicked.connect(self.add_keyword_from_known)

        # --- Right: image panel (selected file) ---
        self.imageBox = QtWidgets.QGroupBox("Image")
        self.imageBox.setStyleSheet(
            "QGroupBox { font-weight: 600; }"
            "QGroupBox::title { subcontrol-origin: margin; left: 8px; padding: 0 6px; }"
        )
        imageLayout = QtWidgets.QVBoxLayout(self.imageBox)
        imageLayout.addWidget(self.selectedLabel)
        imageLayout.addWidget(self.previewLabel)

        mismatchRowW = QtWidgets.QWidget()
        mismatchRow = QtWidgets.QHBoxLayout(mismatchRowW)
        mismatchRow.setContentsMargins(0, 0, 0, 0)
        mismatchRow.addWidget(self.mismatchLabel, 1)
        mismatchRow.addWidget(self.resolveBtn)
        imageLayout.addWidget(mismatchRowW)

        imageLayout.addWidget(QtWidgets.QLabel("Tags on image"))
        imageLayout.addWidget(self.keywordsList, 1)

        addRow = QtWidgets.QHBoxLayout()
        addRow.addWidget(self.addEdit, 1)
        addRow.addWidget(self.addBtn)
        imageLayout.addLayout(addRow)
        imageLayout.addWidget(self.removeBtn)
        imageLayout.addWidget(self.keepBackup)

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
        repoLayout.addWidget(self.knownList, 1)

        leftSplitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical)
        leftSplitter.addWidget(self.files)
        leftSplitter.addWidget(self.repoBox)
        leftSplitter.setStretchFactor(0, 3)
        leftSplitter.setStretchFactor(1, 2)

        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        splitter.addWidget(leftSplitter)
        splitter.addWidget(self.imageBox)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 3)

        self.setCentralWidget(splitter)
        self.statusBar().showMessage("Ready")
        self.resize(1100, 700)

        # Make the whole window feel droppable (not only the file list).
        for w in [
            self,
            self.centralWidget(),
            splitter,
            leftSplitter,
            self.files,
            self.repoBox,
            self.knownList,
            self.imageBox,
            self.previewLabel,
            self.keywordsList,
        ]:
            if w is not None:
                w.setAcceptDrops(True)
                w.installEventFilter(self)

        self.refresh_known_tags()

        # Extra shortcuts (work regardless of focus)
        self._shortcuts: list[QtGui.QShortcut] = []
        self._init_shortcuts()

    def _init_shortcuts(self) -> None:
        sc = QtGui.QShortcut(QtGui.QKeySequence("Backspace"), self)
        sc.activated.connect(self.remove_selected_keywords)
        self._shortcuts.append(sc)

        for seq in ("Ctrl+Return", "Ctrl+Enter"):
            sc = QtGui.QShortcut(QtGui.QKeySequence(seq), self)
            sc.activated.connect(self.add_keyword_from_input)
            self._shortcuts.append(sc)

        sc = QtGui.QShortcut(QtGui.QKeySequence("Ctrl+F"), self)
        sc.activated.connect(self.knownFilter.setFocus)
        self._shortcuts.append(sc)

        sc = QtGui.QShortcut(QtGui.QKeySequence("Ctrl+L"), self)
        sc.activated.connect(self.addEdit.setFocus)
        self._shortcuts.append(sc)

    def eventFilter(self, obj: QtCore.QObject, event: QtCore.QEvent) -> bool:
        et = event.type()
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
        return super().eventFilter(obj, event)

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
        for p in paths:
            p2 = str(Path(p).resolve())
            if p2 in seen:
                continue
            self.files.addItem(p2)
            seen.add(p2)
            added += 1
        self.statusBar().showMessage(f"Added {added} files")
        if added and not self.files.selectedItems():
            self.files.setCurrentRow(0)

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
            self.selectedLabel.setText("Drop JPG/JPEG files here")
            self.mismatchLabel.setText("")
            self.resolveBtn.setEnabled(False)
            self.keywordsList.clear()
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

        worker = Worker(self.exif.read_keywords, current)

        def _ok(st: KeywordState) -> None:
            if token != self._selection_token:
                return
            self._keywords_cache[current] = st
            self._render_keywords(st)
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

        target_w = max(320, self.previewLabel.width())
        target_h = max(220, self.previewLabel.height())

        def _work(p: str) -> QtGui.QImage:
            reader = QtGui.QImageReader(p)
            reader.setAutoTransform(True)
            size = reader.size()
            if size.isValid():
                size.scale(target_w, target_h, QtCore.Qt.AspectRatioMode.KeepAspectRatio)
                reader.setScaledSize(size)
            img = reader.read()
            if img.isNull():
                raise RuntimeError("Failed to load image preview")
            return img

        worker = Worker(_work, path)

        def _ok(img: QtGui.QImage) -> None:
            if token != self._preview_token:
                return
            pm = QtGui.QPixmap.fromImage(img)
            self.previewLabel.setPixmap(pm)
            self.previewLabel.setText("")

        def _err(msg: str) -> None:
            if token != self._preview_token:
                return
            self.previewLabel.setText("No preview")
            self.previewLabel.setPixmap(QtGui.QPixmap())

        worker.signals.finished.connect(_ok)
        worker.signals.error.connect(_err)
        self.pool.start(worker)

    def _render_keywords(self, st: KeywordState) -> None:
        self.keywordsList.clear()
        for kw in st.merged:
            self.keywordsList.addItem(kw)
        if st.mismatch:
            self.mismatchLabel.setText(
                "Warning: IPTC:Keywords and XMP-dc:Subject differ (showing merged view)"
            )
            self.resolveBtn.setEnabled(True)
        else:
            self.mismatchLabel.setText("")
            self.resolveBtn.setEnabled(False)

    def _refresh_current_keywords_view_from_cache(self) -> None:
        sel = self.selected_file_paths()
        if not sel:
            return
        current = sel[0]
        st = self._keywords_cache.get(current)
        if st is None:
            return
        self._render_keywords(st)

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

        try:
            for f in files:
                st = self._ensure_loaded(f)
                merged = dedupe_casefold(st.merged + [tag])
                merged.sort(key=lambda s: s.casefold())
                self.exif.write_keywords([f], merged, keep_backup=self.keepBackup.isChecked())
                self._keywords_cache[f] = KeywordState(merged, merged)
        except ExifToolError as e:
            self._show_error(str(e))
            return

        add_recent_tag(tag)
        self._refresh_current_keywords_view_from_cache()
        self.statusBar().showMessage(f"Added '{tag}' to {len(files)} file(s)")

    def remove_selected_keywords(self) -> None:
        files = self.selected_file_paths()
        if not files:
            self.statusBar().showMessage("No files selected")
            return
        items = self.keywordsList.selectedItems()
        if not items:
            self.statusBar().showMessage("No keywords selected")
            return
        remove = {it.text().strip().casefold() for it in items if it.text().strip()}
        if not remove:
            return

        try:
            for f in files:
                st = self._ensure_loaded(f)
                merged = [k for k in st.merged if k.casefold() not in remove]
                self.exif.write_keywords([f], merged, keep_backup=self.keepBackup.isChecked())
                self._keywords_cache[f] = KeywordState(merged, merged)
        except ExifToolError as e:
            self._show_error(str(e))
            return

        self._refresh_current_keywords_view_from_cache()
        self.statusBar().showMessage(f"Removed {len(remove)} tag(s) from {len(files)} file(s)")

    def force_refresh_known_tags(self) -> None:
        sel = self.selected_file_paths()
        if sel:
            folder = str(Path(sel[0]).resolve().parent)
            self._folder_tag_cache.pop(folder, None)
            self._folder_scans_inflight.discard(folder)
        self.refresh_known_tags()

    def refresh_known_tags(self) -> None:
        filter_text = (self.knownFilter.text() or "").strip().casefold()
        recent = load_recent_tags()

        folder_tags: set[str] = set()
        sel = self.selected_file_paths()
        if sel:
            folder = str(Path(sel[0]).resolve().parent)
            cached = self._folder_tag_cache.get(folder)
            if cached is None:
                self._ensure_folder_scan(folder)
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

    def _ensure_folder_scan(self, folder: str) -> None:
        if folder in self._folder_tag_cache:
            return
        if folder in self._folder_scans_inflight:
            return
        self._folder_scans_inflight.add(folder)

        token = self._selection_token
        self.statusBar().showMessage("Scanning folder tags...")
        worker = Worker(self.exif.scan_folder_tags, folder)

        def _ok(tags: set[str]) -> None:
            self._folder_tag_cache[folder] = tags
            self._folder_scans_inflight.discard(folder)
            if token == self._selection_token:
                self.statusBar().showMessage("Ready")
                self.refresh_known_tags()

        def _err(msg: str) -> None:
            self._folder_tag_cache[folder] = set()
            self._folder_scans_inflight.discard(folder)
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

        def _work(paths: list[str]) -> tuple[int, dict[str, list[str]]]:
            changed = 0
            merged_by_file: dict[str, list[str]] = {}
            for f in paths:
                st = self.exif.read_keywords(f)
                merged = st.merged
                # Only write if fields differ; avoids unnecessary rewrite.
                if st.mismatch:
                    self.exif.write_keywords([f], merged, keep_backup=keep_backup)
                    changed += 1
                merged_by_file[f] = merged
            return changed, merged_by_file

        token = self._selection_token
        worker = Worker(_work, files)

        def _ok(res: tuple[int, dict[str, list[str]]]) -> None:
            changed, merged_by_file = res
            if token == self._selection_token:
                for f, merged in merged_by_file.items():
                    self._keywords_cache[f] = KeywordState(merged, merged)
                self.statusBar().showMessage(f"Resolved {changed} file(s)")
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


def main() -> int:
    app = QtWidgets.QApplication(sys.argv)
    w = MainWindow()
    w.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
