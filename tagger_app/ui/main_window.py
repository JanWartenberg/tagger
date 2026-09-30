import re
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import replace
from pathlib import Path
from typing import TypedDict

from PyQt6 import QtCore, QtGui, QtWidgets

from tagger_app.exif_tool import ExifTool, KeywordState
from tagger_app.file_actions import FilePaneActions
from tagger_app.indexing import (
    DateQueryError,
    IndexSyncResult,
    IptcEmptyIndexResult,
    PhotoIndex,
    resolve_index_root,
    validate_search_query,
)
from tagger_app.indexing import (
    IndexRefreshProgress as IndexRefreshStep,
)
from tagger_app.photo_workspace import (
    PhotoWorkspace,
    PhotoWorkspaceSnapshot,
    PhotoWorkspaceViewMode,
)
from tagger_app.services.background_coordinator import (
    BackgroundCoordinator,
    BackgroundRunner,
    CoordinatorEvent,
    DiscoveryAdapter,
    DiscoveryCompleted,
    DiscoveryEvent,
    DiscoveryKind,
    DiscoveryRequest,
    IndexAdapter,
    IndexEnsureCompleted,
    IndexReadFailed,
    IndexReadKind,
    IndexReadRequest,
    IndexRefreshCompleted,
    IndexRefreshFailed,
    IndexRefreshKind,
    IndexRefreshProgress,
    IndexRefreshRequest,
    IndexSearchCompleted,
    IndexStaleResultEvicted,
    IndexWriteCompleted,
    IndexWriteFailed,
    IptcEmptyIndexCompleted,
    KnownTagsCompleted,
)
from tagger_app.services.batch_tag_summary import (
    BatchTagSummary,
    summarize_batch_tags,
)
from tagger_app.services.duplicate_detection import (
    CandidateGroup,
    DuplicateScanCompleted,
    DuplicateScanCoordinator,
    DuplicateScanFailed,
    DuplicateScanProgress,
    DuplicateScanStarted,
    DuplicateScopeCoordinator,
    DuplicateScopeKind,
    DuplicateScopeSnapshot,
    ExifToolCaptureMetadataReader,
    SameCaptureTimestampDetector,
    ScanResult,
    ScopePreparationCompleted,
    ScopePreparationFailed,
)
from tagger_app.services.error_history import SessionErrorHistory
from tagger_app.services.keyword_limits import (
    iptc_keyword_list_violation,
    keyword_length_violation,
    normalize_keyword,
)
from tagger_app.services.keyword_reconciliation import (
    aligned_keyword_rows,
    reconcile_keywords,
)
from tagger_app.services.pending_tag_mutation import (
    MutationStatus,
    PendingTagMutation,
    TagIntent,
)
from tagger_app.services.photo_discovery import (
    SUPPORTED_PHOTO_EXTENSIONS,
    FileSystemPhotoDiscovery,
)
from tagger_app.services.tag_mutation import TagMutationResult, TagMutationService
from tagger_app.services.tag_mutation_coordinator import (
    TagMutationCoordinator,
    TagMutationLifecycle,
    TagMutationLifecycleKind,
)
from tagger_app.services.tag_propagation import (
    TagPropagationPlan,
    prepare_propagation,
    require_empty_target,
    validate_propagation,
)
from tagger_app.ui.duplicate_copy_preview import DuplicateCopyPreview
from tagger_app.storage import (
    add_recent_tag,
    load_config,
    load_recent_tags,
    save_config,
)
from tagger_app.ui.actions import ActionSpec, KeyRoute, build_action_specs
from tagger_app.ui.tag_completion import TagCompletion
from tagger_app.utils import dedupe_casefold, normalize_path


class DuplicateAssessment(TypedDict):
    source: str | None
    targets: set[str]
    ignored: bool
    submitted: bool
    outcomes: dict[str, str]
    keep_backup: bool


DEFAULT_INDEX_ROOT = Path.home() / "Pictures"
METADATA_READ_DEBOUNCE_MS = 25
PREVIEW_LOAD_DEBOUNCE_MS = 125
FILE_PANE_RENDER_BATCH_SIZE = 250
REFRESH_DISCOVERY_ANIMATION_INTERVAL_MS = 1_000
METADATA_READ_PRIORITY = 1_000_000
_MISSING_FILE_ERROR = re.compile(
    r"\bfile not found\b|\bno such file or directory\b", re.IGNORECASE
)


def _paint_loading_spinner(
    painter: QtGui.QPainter, rect: QtCore.QRectF, angle: int
) -> None:
    """Paint the shared blue indeterminate-spinner treatment."""
    size = min(rect.width(), rect.height())
    painter.save()
    painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
    pen = QtGui.QPen(QtGui.QColor("#0099e5"))
    pen.setWidthF(size * 0.10)
    pen.setCapStyle(QtCore.Qt.PenCapStyle.FlatCap)
    painter.setPen(pen)
    painter.translate(rect.center())
    painter.rotate(angle)
    radius = size * 0.35
    painter.drawArc(
        QtCore.QRectF(-radius, -radius, radius * 2, radius * 2),
        20 * 16,
        270 * 16,
    )
    painter.restore()


def _loading_spinner_icon(size: int, angle: int) -> QtGui.QIcon:
    """Render one file-pane spinner frame without creating a row widget."""
    pixmap = QtGui.QPixmap(size, size)
    pixmap.fill(QtCore.Qt.GlobalColor.transparent)
    painter = QtGui.QPainter(pixmap)
    _paint_loading_spinner(painter, QtCore.QRectF(pixmap.rect()), angle)
    painter.end()
    return QtGui.QIcon(pixmap)


def _unverified_iptc_icon(size: int = 16) -> QtGui.QIcon:
    """Render the compact marker for an unreadable IPTC-empty candidate."""
    pixmap = QtGui.QPixmap(size, size)
    pixmap.fill(QtCore.Qt.GlobalColor.transparent)
    painter = QtGui.QPainter(pixmap)
    painter.setPen(QtGui.QColor("#b45309"))
    font = painter.font()
    font.setBold(True)
    font.setPixelSize(round(size * 0.8))
    painter.setFont(font)
    painter.drawText(pixmap.rect(), QtCore.Qt.AlignmentFlag.AlignCenter, "?")
    painter.end()
    return QtGui.QIcon(pixmap)


class CompactStatusMenuButton(QtWidgets.QToolButton):
    """Keep a native menu button from consuming platform-dependent footer width."""

    MAXIMUM_HINT_WIDTH = 70

    def sizeHint(self) -> QtCore.QSize:
        hint = super().sizeHint()
        hint.setWidth(min(hint.width(), self.MAXIMUM_HINT_WIDTH))
        return hint

    def minimumSizeHint(self) -> QtCore.QSize:
        hint = super().minimumSizeHint()
        hint.setWidth(min(hint.width(), self.MAXIMUM_HINT_WIDTH))
        return hint


class LoadingSpinner(QtWidgets.QWidget):
    """Small indeterminate spinner painted without an external image asset."""

    def __init__(self, size: int = 32, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(size, size)
        self._angle = 0
        self._timer = QtCore.QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._advance)

    def showEvent(self, event: QtGui.QShowEvent) -> None:
        self._timer.start()
        super().showEvent(event)

    def hideEvent(self, event: QtGui.QHideEvent) -> None:
        self._timer.stop()
        super().hideEvent(event)

    def _advance(self) -> None:
        self._angle = (self._angle + 6) % 360
        self.update()

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:
        del event
        painter = QtGui.QPainter(self)
        _paint_loading_spinner(painter, QtCore.QRectF(self.rect()), self._angle)
        painter.end()


class FileListWidget(QtWidgets.QListWidget):
    filesDropped = QtCore.pyqtSignal(list)

    def __init__(self) -> None:
        super().__init__()
        self.setAcceptDrops(True)
        self.setSelectionMode(
            QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection
        )

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
        urls = event.mimeData().urls()
        if urls:
            self.filesDropped.emit(urls)
            event.acceptProposedAction()
        else:
            super().dropEvent(event)


class ResolveKeywordsDialog(QtWidgets.QDialog):
    """Qt adapter for one photo's explicit IPTC/XMP reconciliation choices."""

    _DELETE_STYLE = "color: #dc2626; font-weight: 700;"
    _COPY_STYLE = "color: palette(link); font-weight: 700;"
    _DISABLED_STYLE = "color: #6b7280; font-weight: 700;"

    def __init__(self, state: KeywordState, parent: QtWidgets.QWidget) -> None:
        super().__init__(parent)
        self.setWindowTitle("Resolve IPTC/XMP keywords")
        self.setModal(True)
        self._source = state
        self._reconciliation = reconcile_keywords(state)
        self._iptc = list(self._reconciliation.iptc)
        self._xmp = list(self._reconciliation.xmp)
        self._iptc_readable = state.iptc_readable
        self._xmp_readable = state.xmp_readable
        self._row_values: tuple[tuple[str | None, str | None], ...] = ()
        self._row_frames: list[QtWidgets.QFrame] = []
        self._selected_row = 0
        self._pending_vim_operator: str | None = None
        self._shortcuts: list[QtGui.QShortcut] = []

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(
            QtWidgets.QLabel(
                "IPTC is TAGGER's canonical tag field. Choose each field's final "
                "values; Apply writes both fields once."
            )
        )
        self.policyWarning = QtWidgets.QLabel()
        self.policyWarning.setWordWrap(True)
        self.policyWarning.setStyleSheet("color: #dc2626; font-weight: 700;")
        self.policyWarning.hide()
        layout.addWidget(self.policyWarning)
        self._rows = QtWidgets.QGridLayout()
        self._rows.setColumnStretch(0, 1)
        self._rows.setColumnStretch(5, 1)
        table = QtWidgets.QWidget()
        table.setLayout(self._rows)
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(table)
        layout.addWidget(scroll, 1)

        controls = QtWidgets.QGridLayout()
        controls.setColumnStretch(0, 1)
        controls.setColumnStretch(1, 1)
        if self._reconciliation.can_copy:
            controls.addWidget(
                self._button(
                    ">>", "Copy all IPTC keywords to XMP", self._copy_all_iptc
                ),
                0,
                0,
            )
            controls.addWidget(
                self._button("<<", "Copy all XMP keywords to IPTC", self._copy_all_xmp),
                0,
                1,
            )
            controls.addWidget(
                self._button("× IPTC", "Delete all IPTC keywords", self._clear_iptc),
                1,
                0,
            )
            controls.addWidget(
                self._button("XMP ×", "Delete all XMP keywords", self._clear_xmp),
                1,
                1,
            )
        else:
            unreadable = []
            if not self._iptc_readable:
                unreadable.append("IPTC:Keywords")
            if not self._xmp_readable:
                unreadable.append("XMP-dc:Subject")
            controls.addWidget(
                QtWidgets.QLabel(
                    f"{' and '.join(unreadable)} could not be read. "
                    "Only delete the unreadable field or cancel."
                ),
                0,
                0,
                1,
                2,
            )
            if not self._iptc_readable:
                controls.addWidget(
                    self._button(
                        "× IPTC", "Delete unreadable IPTC field", self._clear_iptc
                    ),
                    1,
                    0,
                )
            if not self._xmp_readable:
                controls.addWidget(
                    self._button(
                        "XMP ×", "Delete unreadable XMP field", self._clear_xmp
                    ),
                    1,
                    1,
                )
        layout.addLayout(controls)

        self.buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Apply
            | QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        self.buttons.clicked.connect(self._handle_dialog_button)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)
        self._install_shortcuts()
        self._render_rows()
        self._update_apply_enabled()

    def _button(
        self, text: str, tooltip: str, callback: Callable[[], None]
    ) -> QtWidgets.QToolButton:
        button = QtWidgets.QToolButton()
        button.setText(text)
        button.setToolTip(tooltip)
        button.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Fixed,
        )
        if "×" in text:
            button.setStyleSheet(self._DELETE_STYLE)
        elif ">" in text or "<" in text or "→" in text or "←" in text:
            button.setStyleSheet(self._COPY_STYLE)
        button.clicked.connect(callback)
        return button

    def _install_shortcuts(self) -> None:
        bindings = (
            ("Alt+A", self._accept_if_allowed),
            ("Alt+C", self.reject),
            ("Escape", self.reject),
            ("j", lambda: self._move_selection(1)),
            ("k", lambda: self._move_selection(-1)),
            ("h", lambda: self._copy_selected(False)),
            ("l", lambda: self._copy_selected(True)),
        )
        for sequence, callback in bindings:
            shortcut = QtGui.QShortcut(QtGui.QKeySequence(sequence), self)
            shortcut.setContext(QtCore.Qt.ShortcutContext.WindowShortcut)
            shortcut.activated.connect(callback)
            self._shortcuts.append(shortcut)

    def _handle_dialog_button(self, button: QtWidgets.QAbstractButton) -> None:
        if (
            self.buttons.standardButton(button)
            is QtWidgets.QDialogButtonBox.StandardButton.Apply
        ):
            self._accept_if_allowed()

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:
        modifiers = event.modifiers()
        if modifiers == QtCore.Qt.KeyboardModifier.AltModifier:
            if event.key() == QtCore.Qt.Key.Key_A:
                self._accept_if_allowed()
                event.accept()
                return
            if event.key() == QtCore.Qt.Key.Key_C:
                self.reject()
                event.accept()
                return
        if event.key() == QtCore.Qt.Key.Key_Escape:
            self.reject()
            event.accept()
            return
        text = event.text()
        if self._pending_vim_operator is not None:
            operator = self._pending_vim_operator
            self._pending_vim_operator = None
            if operator == "d" and text == "d":
                self._delete_selected()
            elif operator == ">" and text == ">":
                self._copy_all_iptc()
            elif operator == "<" and text == "<":
                self._copy_all_xmp()
            event.accept()
            return
        if modifiers == QtCore.Qt.KeyboardModifier.NoModifier:
            key_actions = {
                QtCore.Qt.Key.Key_J: lambda: self._move_selection(1),
                QtCore.Qt.Key.Key_K: lambda: self._move_selection(-1),
                QtCore.Qt.Key.Key_H: lambda: self._copy_selected(False),
                QtCore.Qt.Key.Key_L: lambda: self._copy_selected(True),
            }
            action = key_actions.get(event.key())
            if action is not None:
                action()
                event.accept()
                return
        if text in {"d", ">", "<"}:
            self._pending_vim_operator = text
            QtCore.QTimer.singleShot(600, self._clear_pending_vim_operator)
            event.accept()
            return
        super().keyPressEvent(event)

    def _clear_pending_vim_operator(self) -> None:
        self._pending_vim_operator = None

    def _render_rows(self) -> None:
        self._row_values = aligned_keyword_rows(tuple(self._iptc), tuple(self._xmp))
        self._selected_row = min(self._selected_row, max(0, len(self._row_values) - 1))
        self._row_frames = []
        while self._rows.count():
            item = self._rows.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()
        iptc_heading = QtWidgets.QLabel("IPTC:Keywords · canonical")
        iptc_heading.setStyleSheet("font-weight: 700;")
        xmp_heading = QtWidgets.QLabel("XMP-dc:Subject (compatibility)")
        xmp_heading.setStyleSheet("color: #64748b;")
        self._rows.addWidget(iptc_heading, 0, 0, 1, 3)
        self._rows.addWidget(xmp_heading, 0, 3, 1, 3)
        for row, (iptc, xmp) in enumerate(self._row_values, start=1):
            self._add_row(row, iptc, xmp)
        self._update_selected_row()

    def _add_row(self, row: int, iptc: str | None, xmp: str | None) -> None:
        frame = QtWidgets.QFrame()
        frame.setFrameShape(QtWidgets.QFrame.Shape.StyledPanel)
        row_layout = QtWidgets.QGridLayout(frame)
        row_layout.setContentsMargins(3, 1, 3, 1)
        row_layout.setColumnStretch(0, 1)
        row_layout.setColumnStretch(5, 1)
        iptc_label = QtWidgets.QLabel(iptc or "")
        iptc_label.setStyleSheet(
            "font-weight: 700; border-left: 3px solid palette(highlight); padding: 3px;"
        )
        xmp_label = QtWidgets.QLabel(xmp or "")
        xmp_label.setStyleSheet("color: #64748b; background: #f8fafc; padding: 3px;")
        delete_iptc = self._button(
            "×", "Delete this IPTC keyword", lambda: self._delete(iptc, True)
        )
        copy_to_xmp = self._button(
            "→", "Copy this IPTC keyword to XMP", lambda: self._copy(iptc, True)
        )
        copy_to_iptc = self._button(
            "←", "Copy this XMP keyword to IPTC", lambda: self._copy(xmp, False)
        )
        delete_xmp = self._button(
            "×", "Delete this XMP keyword", lambda: self._delete(xmp, False)
        )
        for button in (delete_iptc, delete_xmp):
            button.setStyleSheet(self._DELETE_STYLE)
        for button in (copy_to_xmp, copy_to_iptc):
            button.setStyleSheet(self._COPY_STYLE)
        self._set_available(delete_iptc, iptc is not None)
        self._set_available(
            copy_to_xmp, iptc is not None and self._reconciliation.can_copy
        )
        self._set_available(
            copy_to_iptc, xmp is not None and self._reconciliation.can_copy
        )
        self._set_available(delete_xmp, xmp is not None)
        row_layout.addWidget(iptc_label, 0, 0)
        row_layout.addWidget(delete_iptc, 0, 1)
        row_layout.addWidget(copy_to_xmp, 0, 2)
        row_layout.addWidget(copy_to_iptc, 0, 3)
        row_layout.addWidget(delete_xmp, 0, 4)
        row_layout.addWidget(xmp_label, 0, 5)
        self._row_frames.append(frame)
        self._rows.addWidget(frame, row, 0, 1, 6)

    def _update_selected_row(self) -> None:
        for index, frame in enumerate(self._row_frames):
            if index == self._selected_row:
                frame.setStyleSheet(
                    "QFrame { border: 1px solid palette(highlight); border-radius: 3px; }"
                )
            else:
                frame.setStyleSheet("QFrame { border: 1px solid transparent; }")

    def _move_selection(self, offset: int) -> None:
        if not self._row_values:
            return
        self._selected_row = (self._selected_row + offset) % len(self._row_values)
        self._update_selected_row()

    def _copy_selected(self, iptc_to_xmp: bool) -> None:
        if not self._row_values:
            return
        iptc, xmp = self._row_values[self._selected_row]
        self._copy(iptc if iptc_to_xmp else xmp, iptc_to_xmp)

    def _delete_selected(self) -> None:
        if not self._row_values:
            return
        iptc, xmp = self._row_values[self._selected_row]
        for value, values in ((iptc, self._iptc), (xmp, self._xmp)):
            if value is not None:
                values[:] = [
                    candidate
                    for candidate in values
                    if candidate.casefold() != value.casefold()
                ]
        self._clear_policy_warning()
        self._render_rows()

    def _set_available(self, button: QtWidgets.QToolButton, available: bool) -> None:
        button.setEnabled(available)
        if not available:
            button.setToolTip("")
            button.setStyleSheet(self._DISABLED_STYLE)

    @staticmethod
    def _add_missing(destination: list[str], value: str) -> None:
        if value.casefold() not in {candidate.casefold() for candidate in destination}:
            destination.append(value)

    def _show_policy_warning(self, value: str, byte_count: int) -> None:
        self.policyWarning.setText(
            f"IPTC keyword {value!r} is {byte_count}/64 UTF-8 bytes"
        )
        self.policyWarning.show()

    def _clear_policy_warning(self) -> None:
        self.policyWarning.hide()
        self.policyWarning.clear()

    def _copy(self, value: str | None, iptc_to_xmp: bool) -> None:
        if value is None:
            return
        if not iptc_to_xmp:
            violation = keyword_length_violation(value)
            if violation is not None:
                self._show_policy_warning(violation.value, violation.utf8_byte_count)
                return
        destination = self._xmp if iptc_to_xmp else self._iptc
        self._add_missing(destination, value)
        self._clear_policy_warning()
        self._render_rows()

    def _copy_all_iptc(self) -> None:
        for keyword in self._iptc:
            self._add_missing(self._xmp, keyword)
        self._clear_policy_warning()
        self._render_rows()

    def _copy_all_xmp(self) -> None:
        violation = iptc_keyword_list_violation(self._xmp)
        if violation is not None:
            self._show_policy_warning(violation.value, violation.utf8_byte_count)
            return
        for keyword in self._xmp:
            self._add_missing(self._iptc, keyword)
        self._clear_policy_warning()
        self._render_rows()

    def _delete(self, value: str | None, iptc: bool) -> None:
        if value is None:
            return
        values = self._iptc if iptc else self._xmp
        values[:] = [
            candidate
            for candidate in values
            if candidate.casefold() != value.casefold()
        ]
        self._clear_policy_warning()
        self._render_rows()

    def _clear_iptc(self) -> None:
        self._iptc = []
        self._iptc_readable = True
        self._clear_policy_warning()
        self._render_rows()
        self._update_apply_enabled()

    def _clear_xmp(self) -> None:
        self._xmp = []
        self._xmp_readable = True
        self._clear_policy_warning()
        self._render_rows()
        self._update_apply_enabled()

    def _update_apply_enabled(self) -> None:
        self.buttons.button(QtWidgets.QDialogButtonBox.StandardButton.Apply).setEnabled(
            self._iptc_readable and self._xmp_readable
        )

    def _accept_if_allowed(self) -> None:
        if not (self._iptc_readable and self._xmp_readable):
            return
        violation = iptc_keyword_list_violation(self._iptc)
        if violation is not None:
            self._show_policy_warning(violation.value, violation.utf8_byte_count)
            return
        self._clear_policy_warning()
        self.accept()

    def chosen_state(self) -> KeywordState:
        return KeywordState(
            self._iptc,
            self._xmp,
            self._source.date_original,
            self._source.date_create,
            self._source.date_xmp_create,
            self._source.date_digitized,
            self._iptc_readable,
            self._xmp_readable,
        )


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
        except Exception as e:  # noqa: BLE001 - worker boundary reports all failures
            self.signals.error.emit(str(e))
            return
        self.signals.finished.emit(res)


class QtBackgroundRunner:
    """Submit coordinator work through TAGGER's existing global thread pool."""

    def __init__(self, pool: QtCore.QThreadPool) -> None:
        self._pool = pool

    def submit(self, work: Callable[[], None]) -> None:
        self._pool.start(Worker(work))


class QtTagMutationRunner:
    """Adapt TAGGER's worker signals to the Qt-free mutation coordinator."""

    def __init__(self, pool: QtCore.QThreadPool) -> None:
        self._pool = pool
        self._workers: set[Worker] = set()

    def submit(
        self,
        work: Callable[[], TagMutationResult],
        on_success: Callable[[TagMutationResult], None],
        on_failure: Callable[[str], None],
    ) -> None:
        worker = Worker(work)
        self._workers.add(worker)

        def complete(result: TagMutationResult) -> None:
            self._workers.discard(worker)
            on_success(result)

        def fail(error: str) -> None:
            self._workers.discard(worker)
            on_failure(error)

        worker.signals.finished.connect(complete)
        worker.signals.error.connect(fail)
        self._pool.start(worker)


class PhotoIndexAdapter:
    """Run PhotoIndex work behind the Coordinator's index-adapter protocol."""

    def __init__(self, exif: ExifTool) -> None:
        self._exif = exif
        self._refresh_roots: set[str] = set()

    def is_initialized(self, root: str) -> bool:
        return PhotoIndex(root).is_initialized()

    def needs_keyword_index_rebuild(self, root: str) -> bool:
        return PhotoIndex(root).needs_keyword_index_rebuild()

    def is_refresh_stale(self, root: str) -> bool:
        return PhotoIndex(root).is_refresh_stale()

    def sync(self, root: str, paths: Sequence[str]) -> object:
        return PhotoIndex(root).sync_paths(self._exif, list(paths))

    def refresh(self, root: str) -> object:
        return self._run_refresh_step(root, restart=False)

    def restart_refresh(self, root: str) -> object:
        self._refresh_roots.discard(root)
        return self._run_refresh_step(root, restart=True)

    def _run_refresh_step(self, root: str, *, restart: bool) -> object:
        index = PhotoIndex(root)
        refresh_step = getattr(index, "refresh_step", None)
        result = (
            refresh_step(self._exif, restart=restart)
            if refresh_step is not None
            else index.sync_root(self._exif)
        )
        was_active = root in self._refresh_roots
        if isinstance(result, IndexRefreshStep):
            self._refresh_roots.add(root)
            return replace(result, resumed=False) if was_active else result
        self._refresh_roots.discard(root)
        return result

    def cancel_refresh(self, root: str) -> bool:
        self._refresh_roots.discard(root)
        cancel = getattr(PhotoIndex(root), "cancel_refresh", None)
        return bool(cancel()) if cancel is not None else False

    def remove_photo(self, root: str, path: str) -> bool:
        return PhotoIndex(root).remove_photo(path)

    def reconcile_directory(self, root: str, directory: str) -> object:
        return PhotoIndex(root).sync_directory(self._exif, directory)

    def index_missing(self, root: str, paths: Sequence[str]) -> int:
        index = PhotoIndex(root)
        normalized_paths = [normalize_path(path) for path in paths]
        existing = index.has_photos(normalized_paths)
        missing = [path for path in normalized_paths if path not in existing]
        if not missing:
            return 0
        index.update_states(self._exif.read_keywords_many(missing))
        return len(missing)

    def update_states(self, root: str, states: Mapping[str, object]) -> None:
        keyword_states = {
            path: state
            for path, state in states.items()
            if isinstance(state, KeywordState)
        }
        PhotoIndex(root).update_states(keyword_states)

    def search(self, root: str, query: str) -> Sequence[str]:
        return PhotoIndex(root).search_photos(query)

    def load_iptc_empty(
        self, root: str, candidate_paths: Sequence[str]
    ) -> IptcEmptyIndexResult:
        return PhotoIndex(root).load_iptc_empty_photos(candidate_paths)

    def load_known_tags(self, root: str) -> set[str]:
        return PhotoIndex(root).load_tags_for_root()


class MainWindow(QtWidgets.QMainWindow):
    backgroundDiscoveryEvent = QtCore.pyqtSignal(object)
    duplicateScopeEvent = QtCore.pyqtSignal(object)
    duplicateScanEvent = QtCore.pyqtSignal(object)

    def __init__(
        self,
        *,
        discovery: DiscoveryAdapter | None = None,
        background_runner: BackgroundRunner | None = None,
        index_adapter: IndexAdapter | None = None,
        file_actions: FilePaneActions | None = None,
    ) -> None:
        super().__init__()
        self.setWindowTitle("TAGGER: Tool Annotator, Grouping Guiding EXIF Records")
        self.setAcceptDrops(True)

        self.exif = ExifTool()
        self._file_actions = file_actions or FilePaneActions()
        self.tag_mutations = TagMutationService(self.exif)
        self._error_history = SessionErrorHistory()
        self.pool = QtCore.QThreadPool.globalInstance()
        self._queued_preview_workers: list[Worker] = []
        self._tag_mutation_coordinator = TagMutationCoordinator(
            runner=QtTagMutationRunner(self.pool),
            event_sink=self._handle_tag_mutation_lifecycle,
        )
        self._keywords_cache: dict[str, KeywordState] = {}
        self._batch_summary_generation = 0
        self._batch_summary_selection: tuple[str, ...] = ()
        self._index_root: str | None = None
        self._index_sync_inflight: set[str] = set()
        self._recent_tags_snapshot = load_recent_tags()
        self._known_tags_snapshot: set[str] = set()
        self._known_tags_root: str | None = None
        self._active_known_tags_request: IndexReadRequest | None = None
        self._active_search_request: IndexReadRequest | None = None
        self._displayed_search_request: IndexReadRequest | None = None
        self._displayed_search_generation: int | None = None
        self._displayed_search_query: str | None = None
        self._active_index_refresh_request: IndexRefreshRequest | None = None
        self._iptc_empty_filter_request: IndexReadRequest | None = None
        self._iptc_empty_refresh_check_request: IndexReadRequest | None = None
        self._iptc_empty_refresh_apply_request: IndexReadRequest | None = None
        self._iptc_empty_filter_operation_id: int | None = None
        self._iptc_empty_root: str | None = None
        self._iptc_empty_waiting_for_index = False
        self._iptc_empty_unknown_paths: set[str] = set()
        self._iptc_empty_refresh_available = False
        self._last_refresh_status_at = 0.0
        self._refresh_discovery_progress: IndexRefreshStep | None = None
        self._refresh_discovery_hidden_letter_index = 0
        self._refresh_discovery_timer = QtCore.QTimer(self)
        self._refresh_discovery_timer.setInterval(
            REFRESH_DISCOVERY_ANIMATION_INTERVAL_MS
        )
        self._refresh_discovery_timer.timeout.connect(
            self._advance_refresh_discovery_animation
        )
        self._stale_result_repairs: dict[str, IndexRefreshRequest] = {}
        self._search_restore_scroll: tuple[str | None, int] | None = None
        self._filename_filter_restore_scroll: tuple[str | None, int] | None = None
        self._directory_exclusion_restore_scroll: tuple[str | None, int] | None = None
        self._selection_token = 0
        self._files_render_token = 0
        self._files_selection_scroll_anchor: tuple[str | None, int] | None = None
        self._files_shift_selection_anchor: int | None = None
        self._files_selection_scroll_restore_timer = QtCore.QTimer(self)
        self._files_selection_scroll_restore_timer.setSingleShot(True)
        self._files_selection_scroll_restore_timer.timeout.connect(
            self._restore_pending_files_selection_scroll_anchor
        )
        self._pending_metadata_read: tuple[int, str] | None = None
        self._metadata_read_in_flight = False
        self._metadata_read_timer = QtCore.QTimer(self)
        self._metadata_read_timer.setSingleShot(True)
        self._metadata_read_timer.setInterval(METADATA_READ_DEBOUNCE_MS)
        self._metadata_read_timer.timeout.connect(self._start_pending_metadata_read)
        self._pending_preview_load: tuple[int, str] | None = None
        self._preview_load_timer = QtCore.QTimer(self)
        self._preview_load_timer.setSingleShot(True)
        self._preview_load_timer.setInterval(PREVIEW_LOAD_DEBOUNCE_MS)
        self._preview_load_timer.timeout.connect(self._start_pending_preview_load)
        self.photo_workspace = PhotoWorkspace()
        self._active_replacement_discovery: DiscoveryRequest | None = None
        self._pending_additive_discoveries: set[int] = set()
        self._coordinator_workspace_generation: int | None = None

        self._config = load_config()
        discovery_adapter = discovery or FileSystemPhotoDiscovery()
        background_runner_adapter = background_runner or QtBackgroundRunner(self.pool)
        self._background_coordinator = BackgroundCoordinator(
            discovery=discovery_adapter,
            index=index_adapter or PhotoIndexAdapter(self.exif),
            runner=background_runner_adapter,
            event_sink=self.backgroundDiscoveryEvent.emit,
        )
        self.backgroundDiscoveryEvent.connect(self._handle_coordinator_event)
        self._prepared_duplicate_scope: DuplicateScopeSnapshot | None = None
        self._duplicate_scope_preparing = False
        self._active_duplicate_scope_request_id: int | None = None
        self._duplicate_scope_coordinator = DuplicateScopeCoordinator(
            discovery=discovery_adapter,
            index_factory=PhotoIndex,
            runner=background_runner_adapter,
            event_sink=self.duplicateScopeEvent.emit,
        )
        self.duplicateScopeEvent.connect(self._handle_duplicate_scope_event)
        self._duplicate_detector = SameCaptureTimestampDetector()
        self._duplicate_scan_coordinator = DuplicateScanCoordinator(
            reader=ExifToolCaptureMetadataReader(self.exif),
            runner=background_runner_adapter,
            event_sink=self.duplicateScanEvent.emit,
        )
        self.duplicateScanEvent.connect(self._handle_duplicate_scan_event)
        self._active_duplicate_scan_id: str | None = None
        self._duplicate_scan_result: ScanResult | None = None
        self._duplicate_assessments: dict[str, DuplicateAssessment] = {}
        self._duplicate_member_controls: dict[
            str, dict[str, tuple[QtWidgets.QRadioButton, QtWidgets.QCheckBox]]
        ] = {}
        self._active_duplicate_group_id: str | None = None
        self._visible_duplicate_group_ids: list[str] = []
        self._duplicate_group_buttons: dict[str, QtWidgets.QPushButton] = {}
        self._duplicate_edit_mode = False
        self._duplicate_mutations: dict[int, tuple[ScanResult, str]] = {}
        self._duplicate_copy_generation = 0
        self._duplicate_copy_workers: set[Worker] = set()
        self._duplicate_copy_preview: DuplicateCopyPreview | None = None
        self._duplicate_preview_generation = 0
        self._duplicate_preview_workers: set[Worker] = set()
        self._duplicate_folder_scope_after_load: str | None = None

        self.files = FileListWidget()
        self._file_items_by_path: dict[str, QtWidgets.QListWidgetItem] = {}
        self.files.filesDropped.connect(self.handle_dropped_urls)
        self.files.itemSelectionChanged.connect(self.on_selection_changed)
        self.files.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
        self.files.customContextMenuRequested.connect(self._show_file_context_menu)
        self.files.setToolTip(
            "Focus: f / Alt+1 / Ctrl+W H · Navigate: j/k, gg/G · "
            "Tags: Ctrl+C / Space y, Ctrl+V / Space p · "
            "Files: Space O/G/C/R"
        )
        self._pending_mutation_spinner_items: dict[str, QtWidgets.QListWidgetItem] = {}
        self._pending_mutation_spinner_angle = 0
        self._pending_mutation_spinner_timer = QtCore.QTimer(self)
        self._pending_mutation_spinner_timer.setInterval(16)
        self._pending_mutation_spinner_timer.timeout.connect(
            self._advance_pending_mutation_spinners
        )
        self.filesPaneMessage = QtWidgets.QLabel(self.files.viewport())
        self.filesPaneMessage.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.filesPaneMessage.setAttribute(
            QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents
        )
        self.filesPaneMessage.hide()
        self.filesPaneLoadingIcon = LoadingSpinner(32, self.files.viewport())
        self.filesPaneLoadingIcon.setAttribute(
            QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents
        )
        self.filesPaneLoadingIcon.hide()
        self._loading_photos_message = "Loading photos…"
        self._loading_photos_hidden_letter_index = 0
        self._files_render_loaded: int | None = None
        self._files_render_total: int | None = None
        self._files_render_hidden_letter_index = 0
        self._loading_photos_timer = QtCore.QTimer(self)
        self._loading_photos_timer.setInterval(120)
        self._loading_photos_timer.timeout.connect(
            self._advance_loading_photos_animation
        )

        self.selectedLabel = QtWidgets.QLabel("Drop JPG/JPEG files here")
        self.selectedLabel.setTextInteractionFlags(
            QtCore.Qt.TextInteractionFlag.TextSelectableByMouse
        )

        self.dateLabel = QtWidgets.QLabel("")
        self.dateLabel.setTextInteractionFlags(
            QtCore.Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.copyDateBtn = QtWidgets.QPushButton("Copy EXIF date → XMP")
        self.copyDateBtn.setToolTip("Copy EXIF DateTimeOriginal to XMP:CreateDate")
        self.copyDateBtn.clicked.connect(self.copy_exif_date_to_xmp)

        self.previewLabel = QtWidgets.QLabel("No preview")
        self.previewLabel.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.previewLabel.setMinimumHeight(220)
        self.previewLabel.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Expanding,
        )
        self.previewLabel.setContentsMargins(8, 8, 8, 8)
        self.previewLabel.setStyleSheet(
            "QLabel { background: palette(window); color: palette(text); "
            "border: 1px solid palette(mid); border-radius: 8px; }"
        )
        self._preview_token = 0
        self._preview_image: QtGui.QImage | None = None
        self.mutationStatusLabel = QtWidgets.QLabel("")
        self.mutationStatusLabel.setStyleSheet("color: #1d4ed8;")
        self.mismatchLabel = QtWidgets.QLabel("")
        self.mismatchLabel.setStyleSheet("color: #b45309;")
        self.resolveBtn = QtWidgets.QPushButton("Resolve IPTC/XMP")
        self.resolveBtn.setEnabled(False)
        self.resolveBtn.clicked.connect(self.resolve_mismatch)
        self.resolveBtn.setToolTip("Resolve IPTC/XMP mismatch (Ctrl+R)")

        self.keywordsList = QtWidgets.QListWidget()
        self.keywordsList.setSelectionMode(
            QtWidgets.QAbstractItemView.SelectionMode.SingleSelection
        )
        self.keywordsList.setToolTip(
            "Focus: l / Alt+3 / Ctrl+W L · Insert: i · Yank: Ctrl+C · Paste: Ctrl+V"
        )
        self.batchOverview = QtWidgets.QWidget()
        self.batchOverview.setObjectName("batchTagOverview")
        batchLayout = QtWidgets.QVBoxLayout(self.batchOverview)
        batchLayout.setContentsMargins(0, 0, 0, 0)
        self.batchRepresentativeLabel = QtWidgets.QLabel()
        self.batchCountLabel = QtWidgets.QLabel()
        self.batchSummaryStatus = QtWidgets.QLabel()
        self.batchSummaryStatus.setStyleSheet("color: #315a7e;")
        self.batchSharedTagsList = QtWidgets.QListWidget()
        self.batchSharedTagsList.setSelectionMode(
            QtWidgets.QAbstractItemView.SelectionMode.SingleSelection
        )
        self.batchPartialTagsLabel = QtWidgets.QLabel()
        self.batchRemoveBtn = QtWidgets.QPushButton("Remove shared tag")
        self.batchRemoveBtn.setEnabled(False)
        self.batchRemoveBtn.clicked.connect(self.remove_shared_batch_tag)
        batchLayout.addWidget(self.batchRepresentativeLabel)
        batchLayout.addWidget(self.batchCountLabel)
        batchLayout.addWidget(self.batchSummaryStatus)
        batchLayout.addWidget(QtWidgets.QLabel("Tags on every selected photo"))
        batchLayout.addWidget(self.batchSharedTagsList, 1)
        batchLayout.addWidget(self.batchRemoveBtn)
        batchLayout.addWidget(self.batchPartialTagsLabel)
        self.batchOverview.hide()

        self.addEdit = QtWidgets.QLineEdit()
        self.addEdit.setPlaceholderText("Add keyword...")
        self.addEdit.textChanged.connect(self._update_add_keyword_limit_feedback)
        self.addEdit.returnPressed.connect(self.add_keyword_from_input)
        self.addEdit.setToolTip(
            "Insert: i · Complete/cycle: Tab · Choose: Left/Right · "
            "Accept completion: Enter · Add: Enter again / Ctrl+Enter"
        )
        self.addBtn = QtWidgets.QPushButton("Add")
        self.addBtn.clicked.connect(self.add_keyword_from_input)
        self.addBtn.setToolTip("Add keyword to selected file(s) (Ctrl+Enter)")
        self.removeBtn = QtWidgets.QPushButton("Remove selected")
        self.removeBtn.clicked.connect(self.remove_selected_keywords)
        self.removeBtn.setToolTip("Remove selected tags from image (Del/Backspace/dd)")

        self.keepBackup = QtWidgets.QCheckBox(
            "Keep *_original backups (exiftool default)"
        )
        self.keepBackup.setChecked(False)
        self.keepBackup.setToolTip(
            "If enabled, exiftool keeps *_original backups (Ctrl+Shift+B)"
        )

        self.onlyUntagged = QtWidgets.QCheckBox("Only without IPTC tags")
        self.onlyUntagged.setToolTip("Show only files without IPTC keywords (Ctrl+E)")
        self.onlyUntagged.toggled.connect(
            lambda _checked: self.apply_iptc_filter_async()
        )
        self.dbSearchEdit = QtWidgets.QLineEdit()
        self.dbSearchEdit.setPlaceholderText("Search tags")
        self.dbSearchEdit.setToolTip("Search indexed tags · Focus: Ctrl+T or Alt+T")
        self.dbSearchEdit.returnPressed.connect(self.apply_db_search)
        self.dbDateSearchEdit = QtWidgets.QLineEdit()
        self.dbDateSearchEdit.setPlaceholderText(
            "YYYY, YYYY-MM, YYYY-MM-DD, range, or unknown"
        )
        self.dbDateSearchEdit.setToolTip(
            "Capture date: YYYY, YYYY-MM, YYYY-MM-DD, "
            "YYYY-MM-DD..YYYY-MM-DD, or unknown · Focus: Ctrl+D or Alt+D"
        )
        self.dbDateSearchEdit.returnPressed.connect(self.apply_db_search)
        self.dbSearchBtn = QtWidgets.QPushButton("S\u0332earch")
        self.dbSearchBtn.clicked.connect(self.apply_db_search)
        self.dbSearchBtn.setToolTip("Apply file filters (Alt+S)")
        self.dbSearchClearBtn = QtWidgets.QPushButton("C\u0332lear")
        self.dbSearchClearBtn.clicked.connect(self.clear_all_filters)
        self.dbSearchClearBtn.setToolTip(
            "Clear all file filters (Alt+C or :clearfilters)"
        )
        self.filenameFilterEdit = QtWidgets.QLineEdit()
        self.filenameFilterEdit.setPlaceholderText("Filter filenames")
        self.filenameFilterEdit.setToolTip(
            "Literal filename substring · Focus: Ctrl+F or Alt+F"
        )
        self._filename_filter_timer = QtCore.QTimer(self)
        self._filename_filter_timer.setSingleShot(True)
        self._filename_filter_timer.setInterval(700)
        self._filename_filter_timer.timeout.connect(self.apply_filename_filter)
        self.filenameFilterEdit.textChanged.connect(self._schedule_filename_filter)
        self.filenameFilterEdit.returnPressed.connect(
            self._apply_filename_filter_and_focus_first
        )
        self.filenameCaseSensitiveBtn = QtWidgets.QPushButton("A\u0332a")
        self.filenameCaseSensitiveBtn.setCheckable(True)
        self.filenameCaseSensitiveBtn.setToolTip("Match filename case exactly (Alt+A)")
        self.filenameCaseSensitiveBtn.toggled.connect(
            self._apply_filename_filter_immediately
        )
        self.directoryExcludeEdit = QtWidgets.QLineEdit()
        self.directoryExcludeEdit.setPlaceholderText("Exclude folder")
        self.directoryExcludeEdit.setToolTip(
            "Exclude an exact ancestor folder name · Focus: Alt+X"
        )
        self.directoryExcludeEdit.returnPressed.connect(self.apply_directory_exclusion)
        self.directoryExcludeError = QtWidgets.QLabel("")
        self.directoryExcludeError.setStyleSheet("color: #b91c1c; font-size: 11px;")
        self.directoryExcludeError.hide()
        self._exclude_directory_escape_shortcut = QtGui.QShortcut(
            QtGui.QKeySequence("Escape"), self.directoryExcludeEdit
        )
        self._exclude_directory_escape_shortcut.setContext(
            QtCore.Qt.ShortcutContext.WidgetShortcut
        )
        self._exclude_directory_escape_shortcut.activated.connect(
            self._discard_directory_exclusion_draft
        )
        self.workspaceCountLabel = QtWidgets.QLabel("0 in workspace")
        self.workspaceCountLabel.setStyleSheet("color: palette(text); font-size: 11px;")
        self.filterSummary = QtWidgets.QWidget()
        self.filterSummaryLayout = QtWidgets.QHBoxLayout(self.filterSummary)
        self.filterSummaryLayout.setContentsMargins(0, 0, 0, 0)
        self.filterSummaryLayout.setSpacing(4)
        self.filterChips = QtWidgets.QWidget()
        self.filterChips.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Maximum,
            QtWidgets.QSizePolicy.Policy.Preferred,
        )
        self.filterChipsLayout = QtWidgets.QHBoxLayout(self.filterChips)
        self.filterChipsLayout.setContentsMargins(0, 0, 0, 0)
        self.filterChipsLayout.setSpacing(4)
        self.filterSummaryLayout.addWidget(self.filterChips)
        self.filterSummaryLayout.addStretch(1)
        self.filterInfoLabel = QtWidgets.QLabel("")
        self.filterInfoLabel.setStyleSheet("color: #315a7e; font-size: 11px;")
        self.filterInfoLabel.setToolTip(
            "Active Photo Workspace conditions and result count"
        )
        self.filterSummaryLayout.addWidget(self.filterInfoLabel)
        self.filterSummary.hide()
        self.filesRenderProgressIcon = LoadingSpinner(16)
        self.filesRenderProgressIcon.setObjectName("filesRenderProgressIcon")
        self.filesRenderProgressIcon.setToolTip("Loading discovered photo paths")
        self.filesRenderProgressLabel = QtWidgets.QLabel("")
        self.filesRenderProgressLabel.setObjectName("filesRenderProgress")
        self.filesRenderProgressLabel.setToolTip("Loading discovered photo paths")
        self.filesRenderProgressCountLabel = QtWidgets.QLabel("")
        self.filesRenderProgressCountLabel.setObjectName("filesRenderProgressCount")
        self.filesRenderProgressCountLabel.setToolTip("Loading discovered photo paths")
        progress_font_metrics = self.filesRenderProgressLabel.fontMetrics()
        self.filesRenderProgressLabel.setFixedWidth(
            progress_font_metrics.horizontalAdvance("Loading")
        )
        self.filesRenderProgressCountLabel.setFixedWidth(
            progress_font_metrics.horizontalAdvance("9 999 999 / 9 999 999")
        )
        self.filesRenderProgress = QtWidgets.QWidget()
        progress_layout = QtWidgets.QHBoxLayout(self.filesRenderProgress)
        progress_layout.setContentsMargins(0, 0, 0, 0)
        progress_layout.setSpacing(4)
        progress_layout.addWidget(self.filesRenderProgressIcon)
        progress_layout.addWidget(self.filesRenderProgressLabel)
        progress_layout.addWidget(self.filesRenderProgressCountLabel)
        self.filesRenderProgress.setFixedWidth(
            24
            + self.filesRenderProgressLabel.width()
            + self.filesRenderProgressCountLabel.width()
        )
        self.filesRenderProgress.setToolTip("Loading discovered photo paths")
        self.filesRenderProgress.hide()

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

        self.previewBox = QtWidgets.QWidget()
        previewLayout = QtWidgets.QVBoxLayout(self.previewBox)
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
        tagsLayout.addWidget(self.mutationStatusLabel)
        tagsLayout.addWidget(mismatchRowW)
        tagsLayout.addWidget(self.batchOverview, 1)

        self.tagsOnImageLabel = QtWidgets.QLabel("Tags on image")
        tagsLayout.addWidget(self.tagsOnImageLabel)
        tagsLayout.addWidget(self.keywordsList, 1)

        addRow = QtWidgets.QHBoxLayout()
        addRow.addWidget(self.addEdit, 1)
        addRow.addWidget(self.addBtn)
        addRow.addWidget(self.removeBtn)
        tagsLayout.addLayout(addRow)
        tagsLayout.addWidget(self.keepBackup)

        rightSplitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical)
        rightSplitter.addWidget(self.previewBox)
        rightSplitter.addWidget(tagsBox)
        rightSplitter.setStretchFactor(0, 2)
        rightSplitter.setStretchFactor(1, 1)
        rightSplitter.setChildrenCollapsible(False)
        imageLayout.addWidget(rightSplitter)

        filesPanel = QtWidgets.QWidget()
        filesLayout = QtWidgets.QVBoxLayout(filesPanel)
        filesLayout.setContentsMargins(0, 0, 0, 0)
        filesLayout.setSpacing(6)
        filesWorkspaceRowW = QtWidgets.QWidget()
        filesWorkspaceRow = QtWidgets.QHBoxLayout(filesWorkspaceRowW)
        filesWorkspaceRow.setContentsMargins(7, 0, 0, 0)
        filesWorkspaceRow.addWidget(self.addFolderBtn)
        filesWorkspaceRow.addWidget(self.workspaceCountLabel)
        self.filesFilterToggleBtn = QtWidgets.QToolButton()
        self.filesFilterToggleBtn.setObjectName("filesFilterToggleBtn")
        self.filesFilterToggleBtn.setToolButtonStyle(
            QtCore.Qt.ToolButtonStyle.ToolButtonIconOnly
        )
        self.filesFilterToggleBtn.clicked.connect(self.toggle_files_filter_block)
        self.filesFilterToggleBtn.setArrowType(QtCore.Qt.ArrowType.DownArrow)
        self.filesFilterToggleBtn.setToolTip("Hide filters")
        self.filesFilterToggleBtn.setAccessibleName("Hide filters")
        filesWorkspaceRow.addWidget(self.filesFilterToggleBtn)
        filesWorkspaceRow.addStretch(1)
        filesLayout.addWidget(filesWorkspaceRowW)

        self.filesFilterBox = QtWidgets.QFrame()
        self.filesFilterBox.setObjectName("filesFilterBox")
        self.filesFilterBox.setStyleSheet(
            "QFrame#filesFilterBox { border: 1px solid palette(midlight); "
            "border-radius: 4px; }"
        )
        filesFilterLayout = QtWidgets.QVBoxLayout(self.filesFilterBox)
        filesFilterLayout.setContentsMargins(7, 7, 7, 7)
        filesFilterLayout.setSpacing(5)
        filesFilterForm = QtWidgets.QFormLayout()
        filesFilterForm.setContentsMargins(0, 0, 0, 0)
        filesFilterForm.setHorizontalSpacing(6)
        filesFilterForm.setVerticalSpacing(5)
        filesFilterForm.setLabelAlignment(
            QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter
        )
        filesFilterForm.addRow("T\u0332ags:", self.dbSearchEdit)
        filesFilterForm.addRow("D\u0332ate:", self.dbDateSearchEdit)
        filenameFilterRowW = QtWidgets.QWidget()
        filenameFilterRow = QtWidgets.QHBoxLayout(filenameFilterRowW)
        filenameFilterRow.setContentsMargins(0, 0, 0, 0)
        filenameFilterRow.addWidget(self.filenameFilterEdit, 1)
        filenameFilterRow.addWidget(self.filenameCaseSensitiveBtn)
        filesFilterForm.addRow("F\u0332ilename:", filenameFilterRowW)
        filesFilterForm.addRow("Ex\u0332clude folder:", self.directoryExcludeEdit)
        filesFilterForm.addRow("", self.directoryExcludeError)
        filesFilterForm.addRow(self.onlyUntagged)
        filesFilterLayout.addLayout(filesFilterForm)
        filesFilterActions = QtWidgets.QHBoxLayout()
        filesFilterActions.setContentsMargins(0, 0, 0, 0)
        filesFilterActions.addWidget(self.dbSearchBtn, 1)
        filesFilterActions.addWidget(self.dbSearchClearBtn, 1)
        filesFilterLayout.addLayout(filesFilterActions)
        filesLayout.addWidget(self.filesFilterBox)
        self.filterSummaryLayout.addWidget(self.filesRenderProgress)
        filesLayout.addWidget(self.filterSummary)
        filesLayout.addWidget(self.files, 1)

        filesPanel.setMinimumWidth(250)
        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        splitter.addWidget(filesPanel)
        splitter.addWidget(self.imageBox)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        splitter.setChildrenCollapsible(False)

        self.taggingWorkspaceView = splitter
        self.duplicateReviewView = self._build_duplicate_review_view()
        self.mainViews = QtWidgets.QStackedWidget()
        self.mainViews.setObjectName("mainViews")
        self.mainViews.addWidget(self.taggingWorkspaceView)
        self.mainViews.addWidget(self.duplicateReviewView)
        self.setCentralWidget(self.mainViews)
        self._tagging_focus_widget: QtWidgets.QWidget | None = None

        self.iptcEmptyRefreshOffer = QtWidgets.QWidget()
        self.iptcEmptyRefreshOffer.setObjectName("iptcEmptyRefreshOffer")
        refresh_offer_layout = QtWidgets.QHBoxLayout(self.iptcEmptyRefreshOffer)
        refresh_offer_layout.setContentsMargins(0, 0, 0, 0)
        self.iptcEmptyRefreshLabel = QtWidgets.QLabel(
            "Index updated — IPTC-empty results changed."
        )
        self.iptcEmptyRefreshButton = QtWidgets.QPushButton("Refresh now")
        self.iptcEmptyRefreshButton.clicked.connect(self.refresh_iptc_empty_view)
        refresh_offer_layout.addWidget(self.iptcEmptyRefreshLabel)
        refresh_offer_layout.addWidget(self.iptcEmptyRefreshButton)
        self.iptcEmptyRefreshOffer.hide()
        self.statusBar().addPermanentWidget(self.iptcEmptyRefreshOffer)
        self.indexRepairStatusLabel = QtWidgets.QLabel()
        self.indexRepairStatusLabel.setObjectName("indexRepairStatus")
        self.statusBar().addPermanentWidget(self.indexRepairStatusLabel)
        self.viewSelector = CompactStatusMenuButton()
        self.viewSelector.setObjectName("viewSelector")
        self.viewSelector.setText("Views")
        self.viewSelector.setAutoRaise(True)
        self.viewSelector.setPopupMode(
            QtWidgets.QToolButton.ToolButtonPopupMode.InstantPopup
        )
        self.viewSelector.setToolTip("Switch between tagging and duplicate review")
        self.viewSelector.setAccessibleName("Current application view: Tagging")
        view_menu = QtWidgets.QMenu(self.viewSelector)
        self.taggingViewAction = view_menu.addAction("Tagging workspace")
        self.duplicateReviewAction = view_menu.addAction("Duplicate review")
        self.taggingViewAction.setCheckable(True)
        self.duplicateReviewAction.setCheckable(True)
        self._viewActionGroup = QtGui.QActionGroup(self)
        self._viewActionGroup.setExclusive(True)
        self._viewActionGroup.addAction(self.taggingViewAction)
        self._viewActionGroup.addAction(self.duplicateReviewAction)
        self.taggingViewAction.setChecked(True)
        self.taggingViewAction.triggered.connect(self.show_tagging_workspace)
        self.duplicateReviewAction.triggered.connect(self.show_duplicate_review)
        self.viewSelector.setMenu(view_menu)
        self.statusBar().addPermanentWidget(self.viewSelector)
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
        self._cmdHint.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter
        )
        self._cmdHint.setStyleSheet(
            "QLabel { background: palette(window); border: 1px solid palette(mid); "
            "border-radius: 4px; padding: 2px 6px; }"
        )

        self._tagHint = TagCompletion(self.addEdit, self._tag_candidates, self)

        self._apply_focus_styles()
        self._update_view_indicator(self.photo_workspace.snapshot())

        # Make the whole window feel droppable (not only the file list).
        for w in [
            self,
            self.centralWidget(),
            splitter,
            self.files,
            self.files.viewport(),
            filesPanel,
            self.imageBox,
            self.previewLabel,
            self.keywordsList,
            self.keywordsList.viewport(),
            self.addEdit,
            self.cmdLine,
            self.duplicateReviewView,
            self.duplicateReviewBackButton,
            self.duplicateScopeCombo,
            self.duplicateStartScanButton,
        ]:
            if w is not None:
                w.setAcceptDrops(True)
                w.installEventFilter(self)

        self.refresh_known_tags()

        # Extra shortcuts (work regardless of focus)
        self._shortcuts: list[QtGui.QShortcut] = []
        self._vim_sequence_pending: dict[str, int] = {}
        self._vim_space_pending: int | None = None
        self._vim_visual_keywords = False
        self._vim_visual_anchor = 0
        self._yanked_tags: list[str] = []
        self._actions_by_id: dict[str, ActionSpec] = {}
        self._commands_by_name: dict[str, ActionSpec] = {}
        self._listed_actions: list[ActionSpec] = []
        self._widget_refs: dict[str, QtCore.QObject] = {}
        self._init_actions()

    def _build_duplicate_review_view(self) -> QtWidgets.QWidget:
        view = QtWidgets.QWidget()
        view.setObjectName("duplicateReviewView")
        layout = QtWidgets.QVBoxLayout(view)
        layout.setContentsMargins(12, 10, 12, 12)
        layout.setSpacing(10)

        header = QtWidgets.QHBoxLayout()
        self.duplicateReviewBackButton = QtWidgets.QToolButton()
        self.duplicateReviewBackButton.setText("← Back to tagging")
        self.duplicateReviewBackButton.setToolTip(
            "Return to the tagging workspace (Esc / gT / Ctrl+Alt+T)"
        )
        self.duplicateReviewBackButton.clicked.connect(self.show_tagging_workspace)
        header.addWidget(self.duplicateReviewBackButton)
        title = QtWidgets.QLabel("Duplicate review")
        title_font = title.font()
        title_font.setPointSize(title_font.pointSize() + 2)
        title_font.setBold(True)
        title.setFont(title_font)
        header.addWidget(title)
        header.addStretch(1)
        self.duplicateAddFolderButton = QtWidgets.QPushButton("Add folder")
        self.duplicateAddFolderButton.setToolTip(
            "Add all JPG/JPEG files from a folder (Ctrl+O)"
        )
        self.duplicateAddFolderButton.clicked.connect(self.add_folder_dialog)
        header.addWidget(self.duplicateAddFolderButton)
        read_only = QtWidgets.QLabel("Read-only assessment view")
        read_only.setStyleSheet("color: palette(mid);")
        header.addWidget(read_only)
        layout.addLayout(header)

        content = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical)
        setup = QtWidgets.QGroupBox("Scan setup")
        setup_layout = QtWidgets.QFormLayout(setup)
        self.duplicateScopeCombo = QtWidgets.QComboBox()
        self.duplicateScopeCombo.setToolTip("Choose duplicate scan scope (Alt+S)")
        self.duplicateScopeCombo.addItem(
            "Current index database", DuplicateScopeKind.INDEX_DATABASE
        )
        self.duplicateScopeCombo.addItem(
            "Choose subfolder…", DuplicateScopeKind.SUBFOLDER
        )
        self.duplicateScopeCombo.currentIndexChanged.connect(
            self._duplicate_scope_choice_changed
        )
        setup_layout.addRow("Scope:", self.duplicateScopeCombo)
        self.duplicateScopePathLabel = QtWidgets.QLabel("No active index database")
        self.duplicateScopePathLabel.setWordWrap(True)
        setup_layout.addRow("Location:", self.duplicateScopePathLabel)
        self.duplicateScopeSizeLabel = QtWidgets.QLabel("Waiting for a photo folder")
        setup_layout.addRow("Scope size:", self.duplicateScopeSizeLabel)
        setup_layout.addRow("Method:", QtWidgets.QLabel("Same capture timestamp"))
        self.duplicateScanCostLabel = QtWidgets.QLabel(
            "Choose or add a photo folder to calculate the scan size."
        )
        self.duplicateScanCostLabel.setWordWrap(True)
        setup_layout.addRow("Scan work:", self.duplicateScanCostLabel)
        self.duplicateStartScanButton = QtWidgets.QPushButton("Start scan")
        self.duplicateStartScanButton.setEnabled(False)
        self.duplicateStartScanButton.setToolTip(
            "Scan the prepared scope for candidates (Space s)"
        )
        self.duplicateStartScanButton.clicked.connect(self.start_duplicate_scan)
        setup_layout.addRow(self.duplicateStartScanButton)
        self.duplicateCancelScanButton = QtWidgets.QPushButton("Cancel scan")
        self.duplicateCancelScanButton.setToolTip("Cancel the active scan (Esc)")
        self.duplicateCancelScanButton.setEnabled(False)
        self.duplicateCancelScanButton.clicked.connect(self.cancel_duplicate_scan)
        setup_layout.addRow(self.duplicateCancelScanButton)
        self.duplicateScanProgress = QtWidgets.QProgressBar()
        self.duplicateScanProgress.setRange(0, 1)
        self.duplicateScanProgress.setValue(0)
        self.duplicateScanProgress.setFormat("%v / %m photos")
        self.duplicateScanProgress.hide()
        setup_layout.addRow("Progress:", self.duplicateScanProgress)
        setup_layout.setFieldGrowthPolicy(
            QtWidgets.QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow
        )

        results = QtWidgets.QWidget()
        results_layout = QtWidgets.QVBoxLayout(results)
        results_layout.setContentsMargins(0, 0, 0, 0)
        self.duplicateReviewEmpty = QtWidgets.QWidget()
        empty_layout = QtWidgets.QVBoxLayout(self.duplicateReviewEmpty)
        empty_layout.addStretch(1)
        self.duplicateReviewEmptyTitle = QtWidgets.QLabel(
            "No candidate scan has been started"
        )
        self.duplicateReviewEmptyTitle.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        empty_title_font = self.duplicateReviewEmptyTitle.font()
        empty_title_font.setPointSize(empty_title_font.pointSize() + 2)
        empty_title_font.setBold(True)
        self.duplicateReviewEmptyTitle.setFont(empty_title_font)
        empty_layout.addWidget(self.duplicateReviewEmptyTitle)
        self.duplicateReviewEmptyDetail = QtWidgets.QLabel(
            "Add a photo folder or choose a scan scope. TAGGER will collect its "
            "photo paths before you explicitly start metadata scanning."
        )
        self.duplicateReviewEmptyDetail.setWordWrap(True)
        self.duplicateReviewEmptyDetail.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignCenter
        )
        empty_layout.addWidget(self.duplicateReviewEmptyDetail)
        empty_layout.addStretch(1)
        results_layout.addWidget(self.duplicateReviewEmpty)

        result_summary = QtWidgets.QWidget()
        result_summary_layout = QtWidgets.QHBoxLayout(result_summary)
        result_summary_layout.setContentsMargins(0, 0, 0, 0)
        self.duplicateResultsSummary = QtWidgets.QLabel()
        self.duplicateResultsSummary.setWordWrap(True)
        self.duplicateResultsSummary.hide()
        result_summary_layout.addWidget(self.duplicateResultsSummary, 1)
        self.duplicateExcludeEmptyCandidatesCheck = QtWidgets.QCheckBox(
            "Hide groups where no photo has tags"
        )
        self.duplicateExcludeEmptyCandidatesCheck.setToolTip(
            "Hide groups only when every member has a readable, empty IPTC tag "
            "list (Alt+E)"
        )
        self.duplicateExcludeEmptyCandidatesCheck.toggled.connect(
            self._filter_duplicate_candidates
        )
        self.duplicateExcludeEmptyCandidatesCheck.setEnabled(False)
        result_summary_layout.addWidget(self.duplicateExcludeEmptyCandidatesCheck)
        results_layout.addWidget(result_summary)

        self.duplicateCandidateQueue = QtWidgets.QScrollArea()
        self.duplicateCandidateQueue.setWidgetResizable(True)
        self.duplicateCandidateQueue.setHorizontalScrollBarPolicy(
            QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self.duplicateCandidateQueue.setVerticalScrollBarPolicy(
            QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.duplicateCandidateQueue.setMaximumHeight(104)
        self.duplicateCandidateQueueBody = QtWidgets.QWidget()
        self.duplicateCandidateQueueLayout = QtWidgets.QHBoxLayout(
            self.duplicateCandidateQueueBody
        )
        self.duplicateCandidateQueueLayout.setContentsMargins(6, 6, 6, 6)
        self.duplicateCandidateQueueLayout.setSpacing(6)
        self.duplicateCandidateQueueLayout.addStretch(1)
        self.duplicateCandidateQueue.setWidget(self.duplicateCandidateQueueBody)
        self.duplicateCandidateQueue.hide()
        results_layout.addWidget(self.duplicateCandidateQueue)

        self.duplicateStatusRows = QtWidgets.QWidget()
        self.duplicateStatusRowsLayout = QtWidgets.QVBoxLayout(self.duplicateStatusRows)
        self.duplicateStatusRowsScroll = QtWidgets.QScrollArea()
        self.duplicateStatusRowsScroll.setWidgetResizable(True)
        self.duplicateStatusRowsScroll.setMaximumHeight(160)
        self.duplicateStatusRowsScroll.setWidget(self.duplicateStatusRows)
        self.duplicateStatusRowsScroll.hide()
        results_layout.addWidget(self.duplicateStatusRowsScroll)

        self.duplicateResultsScroll = QtWidgets.QScrollArea()
        self.duplicateResultsScroll.setWidgetResizable(True)
        self.duplicateResultsBody = QtWidgets.QWidget()
        self.duplicateResultsLayout = QtWidgets.QVBoxLayout(self.duplicateResultsBody)
        self.duplicateResultsLayout.addStretch(1)
        self.duplicateResultsScroll.setWidget(self.duplicateResultsBody)
        self.duplicateResultsScroll.hide()
        results_layout.addWidget(self.duplicateResultsScroll, 1)

        self.duplicateAssessmentActions = QtWidgets.QWidget()
        assessment_actions_layout = QtWidgets.QHBoxLayout(
            self.duplicateAssessmentActions
        )
        assessment_actions_layout.setContentsMargins(0, 0, 0, 0)
        self.duplicateAssessmentHint = QtWidgets.QLabel(
            "Choose a tagged source and empty targets, then preview the copy."
        )
        self.duplicateAssessmentHint.setWordWrap(True)
        assessment_actions_layout.addWidget(self.duplicateAssessmentHint, 1)
        self.duplicateEditModeButton = QtWidgets.QPushButton("Edit mode: off (e)")
        self.duplicateEditModeButton.clicked.connect(self.toggle_duplicate_edit_mode)
        assessment_actions_layout.addWidget(self.duplicateEditModeButton)
        self.duplicateEditModeButton.installEventFilter(self)
        self.duplicateIgnoreButton = QtWidgets.QPushButton("Ignore candidate (i)")
        self.duplicateIgnoreButton.setToolTip(
            "Ignore this group for this scan (i in Edit mode); reopen its Ignored row to restore"
        )
        self.duplicateIgnoreButton.clicked.connect(self.ignore_active_duplicate_group)
        assessment_actions_layout.addWidget(self.duplicateIgnoreButton)
        self.duplicateApplyTagsButton = QtWidgets.QPushButton("Copy tags… (c)")
        self.duplicateApplyTagsButton.setEnabled(False)
        self.duplicateApplyTagsButton.setToolTip(
            "Preview copied tags (c in Edit mode); y confirms, n / Esc cancels"
        )
        self.duplicateApplyTagsButton.installEventFilter(self)
        self.duplicateIgnoreButton.installEventFilter(self)
        self.duplicateApplyTagsButton.clicked.connect(self.preview_duplicate_copy)
        assessment_actions_layout.addWidget(self.duplicateApplyTagsButton)
        self.duplicateAssessmentActions.hide()
        results_layout.addWidget(self.duplicateAssessmentActions)

        content.addWidget(setup)
        content.addWidget(results)
        content.setStretchFactor(0, 0)
        content.setStretchFactor(1, 1)
        content.setChildrenCollapsible(False)
        layout.addWidget(content, 1)
        return view

    def _duplicate_scope_choice_changed(self) -> None:
        self._duplicate_scope_coordinator.invalidate()
        self._duplicate_scan_coordinator.cancel()
        self._active_duplicate_scan_id = None
        self._duplicate_scan_result = None
        self._clear_duplicate_results()
        self._prepared_duplicate_scope = None
        self._duplicate_scope_preparing = False
        self._active_duplicate_scope_request_id = None
        self.duplicateScopeSizeLabel.setText("Collecting photo list…")
        self.duplicateStartScanButton.setEnabled(False)
        self.duplicateCancelScanButton.setEnabled(False)
        self.duplicateScanProgress.hide()
        self.duplicateReviewEmptyTitle.setText("Collecting the photo list…")
        self.duplicateReviewEmptyDetail.setText(
            "TAGGER is determining which photos belong to this scope. Large "
            "folders may take some time; metadata scanning has not started."
        )
        self._refresh_duplicate_scope_controls()
        self._ensure_duplicate_scope_prepared()

    def _refresh_duplicate_scope_controls(self) -> None:
        kind = self.duplicateScopeCombo.currentData()
        prepared = self._prepared_duplicate_scope
        if prepared is not None and prepared.kind is kind:
            count = len(prepared.paths)
            self.duplicateScopePathLabel.setText(prepared.root)
            self.duplicateScopeSizeLabel.setText(f"{count:,} photos ready")
            self.duplicateScanCostLabel.setText(
                f"Starting the scan will read metadata from {count:,} photos and "
                "may take some time. Progress and cancellation remain available."
            )
            self.duplicateStartScanButton.setEnabled(
                self._active_duplicate_scan_id is None and bool(prepared.paths)
            )
            return
        self.duplicateStartScanButton.setEnabled(False)
        if self._duplicate_scope_preparing:
            self.duplicateScopeSizeLabel.setText("Collecting photo list…")
            self.duplicateScanCostLabel.setText(
                "Collecting photo paths in the background. Large folders may take "
                "some time; candidate metadata is not being scanned yet."
            )
            return
        if kind is DuplicateScopeKind.INDEX_DATABASE:
            self.duplicateScopePathLabel.setText(
                self._index_root or "No active index database"
            )
            self.duplicateScopeSizeLabel.setText("Waiting for a photo folder")
            self.duplicateScanCostLabel.setText(
                "Add a photo folder to calculate how many photos will be scanned."
            )
        else:
            self.duplicateScopePathLabel.setText("No subfolder selected")
            self.duplicateScopeSizeLabel.setText("Choose a subfolder")
            self.duplicateScanCostLabel.setText(
                "Choose a subfolder to calculate how many photos will be scanned."
            )

    def _invalidate_duplicate_scope_for_folder_load(self) -> None:
        self._duplicate_scope_coordinator.invalidate()
        self._duplicate_scan_coordinator.cancel()
        self._active_duplicate_scan_id = None
        self._active_duplicate_scope_request_id = None
        self._duplicate_scope_preparing = False
        self._prepared_duplicate_scope = None
        self._duplicate_scan_result = None
        self._clear_duplicate_results()
        self.duplicateStartScanButton.setEnabled(False)
        self.duplicateCancelScanButton.setEnabled(False)
        self.duplicateScanProgress.hide()
        self.duplicateScopeSizeLabel.setText("Loading folder…")
        self.duplicateScanCostLabel.setText(
            "Loading the selected folder before calculating its duplicate scan size."
        )

    def _prepare_discovered_duplicate_subfolder(
        self, root: str, paths: tuple[str, ...]
    ) -> None:
        self._duplicate_scope_coordinator.invalidate()
        self.duplicateScopeCombo.blockSignals(True)
        self.duplicateScopeCombo.setCurrentIndex(1)
        self.duplicateScopeCombo.blockSignals(False)
        request = self._duplicate_scope_coordinator.prepare_discovered_subfolder(
            root, paths
        )
        self._active_duplicate_scope_request_id = request.request_id
        self._prepared_duplicate_scope = None
        self._duplicate_scope_preparing = True
        self.duplicateScopePathLabel.setText(normalize_path(root))
        self.duplicateScopeSizeLabel.setText("Collecting photo list…")
        self.duplicateScanCostLabel.setText(
            "Freezing the photos found in the selected subfolder. Metadata scanning "
            "has not started."
        )
        self.duplicateStartScanButton.setEnabled(False)

    def _ensure_duplicate_scope_prepared(self) -> None:
        if (
            self._duplicate_scope_preparing
            or self._active_duplicate_scan_id is not None
        ):
            return
        kind = self.duplicateScopeCombo.currentData()
        prepared = self._prepared_duplicate_scope
        if prepared is not None and prepared.kind is kind:
            return
        if kind is DuplicateScopeKind.INDEX_DATABASE:
            if self._index_root is None:
                self._refresh_duplicate_scope_controls()
                return
            if self._index_root in self._index_sync_inflight:
                self.duplicateScopeSizeLabel.setText("Indexing photos…")
                self.duplicateScanCostLabel.setText(
                    "Updating the photo index before calculating scan size. This "
                    "runs in the background and may take some time."
                )
                return
        self.prepare_duplicate_scope()

    def prepare_duplicate_scope(self) -> None:
        if self._duplicate_scope_preparing:
            return
        self._duplicate_scan_coordinator.cancel()
        self._active_duplicate_scan_id = None
        self._duplicate_scan_result = None
        self._clear_duplicate_results()
        self.duplicateCancelScanButton.setEnabled(False)
        self.duplicateScanProgress.hide()
        kind = self.duplicateScopeCombo.currentData()
        if kind is DuplicateScopeKind.INDEX_DATABASE:
            if self._index_root is None:
                self._refresh_duplicate_scope_controls()
                return
            root = self._index_root
            request = self._duplicate_scope_coordinator.prepare_index(root)
        else:
            root = QtWidgets.QFileDialog.getExistingDirectory(
                self, "Choose duplicate scan folder"
            )
            if not root:
                self.duplicateScopeCombo.blockSignals(True)
                self.duplicateScopeCombo.setCurrentIndex(0)
                self.duplicateScopeCombo.blockSignals(False)
                self._refresh_duplicate_scope_controls()
                self._ensure_duplicate_scope_prepared()
                return
            request = self._duplicate_scope_coordinator.prepare_subfolder(root)
        self._active_duplicate_scope_request_id = request.request_id
        self._prepared_duplicate_scope = None
        self._duplicate_scope_preparing = True
        self.duplicateScopePathLabel.setText(normalize_path(root))
        self.duplicateScopeSizeLabel.setText("Collecting photo list…")
        self.duplicateScanCostLabel.setText(
            "Collecting photo paths in the background. Large folders may take some "
            "time; candidate metadata is not being scanned yet."
        )
        self.duplicateReviewEmptyTitle.setText("Collecting the photo list…")
        self.duplicateReviewEmptyDetail.setText(
            "TAGGER is determining the scan size. This may take some time for a "
            "large folder; no photo metadata is being read yet."
        )
        self.duplicateStartScanButton.setEnabled(False)
        self.statusBar().showMessage("Collecting duplicate scan photo paths…")

    def _handle_duplicate_scope_event(
        self, event: ScopePreparationCompleted | ScopePreparationFailed
    ) -> None:
        if event.request.request_id != self._active_duplicate_scope_request_id:
            return
        self._active_duplicate_scope_request_id = None
        self._duplicate_scope_preparing = False
        if isinstance(event, ScopePreparationFailed):
            self._prepared_duplicate_scope = None
            self.duplicateScopeSizeLabel.setText("Photo list failed")
            self.duplicateScanCostLabel.setText(
                "The scan size could not be calculated. Choose the scope again to "
                "retry."
            )
            self.duplicateReviewEmptyTitle.setText("Could not collect photo list")
            self.duplicateReviewEmptyDetail.setText(event.error)
            self.duplicateStartScanButton.setEnabled(False)
            self.statusBar().showMessage(
                f"Duplicate photo-list collection failed: {event.error}"
            )
            self._record_session_error("Duplicate scope", event.error)
            return
        self._prepared_duplicate_scope = event.snapshot
        count = len(event.snapshot.paths)
        self.duplicateScopePathLabel.setText(event.snapshot.root)
        self.duplicateScopeSizeLabel.setText(f"{count:,} photos ready")
        self.duplicateScanCostLabel.setText(
            f"Starting the scan will read metadata from {count:,} photos and may "
            "take some time. Progress and cancellation remain available."
        )
        self.duplicateReviewEmptyTitle.setText("Ready to scan candidates")
        self.duplicateReviewEmptyDetail.setText(
            f"TAGGER found {count:,} photos in this scope. Start scan will read "
            "their metadata to find candidate groups; no files will be changed."
        )
        self.duplicateStartScanButton.setEnabled(count > 0)
        self.statusBar().showMessage(f"Duplicate scan ready: {count:,} photos")

    def start_duplicate_scan(self) -> None:
        snapshot = self._prepared_duplicate_scope
        if snapshot is None or not snapshot.paths:
            return
        self._duplicate_scan_result = None
        self._clear_duplicate_results()
        self.duplicateReviewEmpty.show()
        self.duplicateReviewEmptyTitle.setText("Scanning candidate evidence…")
        self.duplicateReviewEmptyDetail.setText(
            f"{self._duplicate_detector.display_name} is reading confirmed metadata "
            f"for {len(snapshot.paths):,} frozen photo paths."
        )
        self.duplicateStartScanButton.setEnabled(False)
        self.duplicateCancelScanButton.setEnabled(True)
        self.duplicateScanProgress.setRange(0, len(snapshot.paths))
        self.duplicateScanProgress.setValue(0)
        self.duplicateScanCostLabel.setText(
            f"Scanning metadata for {len(snapshot.paths):,} photos. This may take "
            "some time; you can cancel without publishing partial results."
        )
        self.duplicateScanProgress.show()
        request = self._duplicate_scan_coordinator.start(
            snapshot, self._duplicate_detector
        )
        self._active_duplicate_scan_id = request.scan_id

    def cancel_duplicate_scan(self) -> None:
        if self._active_duplicate_scan_id is None:
            return
        self._duplicate_scan_coordinator.cancel()
        self._active_duplicate_scan_id = None
        self.duplicateCancelScanButton.setEnabled(False)
        self.duplicateScanProgress.hide()
        self.duplicateReviewEmptyTitle.setText("Candidate scan cancelled")
        self.duplicateReviewEmptyDetail.setText(
            "The cancelled scan cannot publish results. The prepared scope remains "
            "available for another explicit scan."
        )
        self._refresh_duplicate_scope_controls()
        self.statusBar().showMessage("Duplicate candidate scan cancelled")

    def _handle_duplicate_scan_event(
        self,
        event: DuplicateScanStarted
        | DuplicateScanProgress
        | DuplicateScanCompleted
        | DuplicateScanFailed,
    ) -> None:
        if isinstance(event, DuplicateScanStarted):
            self._active_duplicate_scan_id = event.request.scan_id
            self.statusBar().showMessage(
                f"Running {self._duplicate_detector.display_name}…"
            )
            return
        if event.request.scan_id != self._active_duplicate_scan_id:
            return
        if isinstance(event, DuplicateScanProgress):
            self.duplicateScanProgress.setMaximum(event.progress.total)
            self.duplicateScanProgress.setValue(event.progress.processed)
            return
        self._active_duplicate_scan_id = None
        self.duplicateCancelScanButton.setEnabled(False)
        self.duplicateScanProgress.hide()
        self._refresh_duplicate_scope_controls()
        if isinstance(event, DuplicateScanFailed):
            self.duplicateReviewEmpty.show()
            self.duplicateReviewEmptyTitle.setText("Candidate scan failed")
            self.duplicateReviewEmptyDetail.setText(event.error)
            self._record_session_error("Duplicate scan", event.error)
            self.statusBar().showMessage(f"Duplicate scan failed: {event.error}")
            return
        self._duplicate_scan_result = event.result
        self._render_duplicate_scan_result(event.result)
        self.statusBar().showMessage(
            f"Duplicate scan complete: {len(event.result.groups):,} candidate groups"
        )

    @staticmethod
    def _clear_layout(layout: QtWidgets.QLayout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
            child_layout = item.layout()
            if child_layout is not None:
                MainWindow._clear_layout(child_layout)

    def _clear_duplicate_results(self) -> None:
        self._invalidate_duplicate_copy()
        self._duplicate_preview_generation += 1
        self._duplicate_assessments.clear()
        self._clear_layout(self.duplicateStatusRowsLayout)
        self.duplicateStatusRowsScroll.hide()
        self._duplicate_member_controls.clear()
        self._active_duplicate_group_id = None
        self._visible_duplicate_group_ids.clear()
        self._duplicate_group_buttons.clear()
        self._clear_layout(self.duplicateCandidateQueueLayout)
        self.duplicateCandidateQueueLayout.addStretch(1)
        self._clear_layout(self.duplicateResultsLayout)
        self.duplicateResultsLayout.addStretch(1)
        self.duplicateResultsSummary.hide()
        self.duplicateExcludeEmptyCandidatesCheck.setEnabled(False)
        self.duplicateCandidateQueue.hide()
        self.duplicateResultsScroll.hide()
        self.duplicateAssessmentActions.hide()

    def _render_duplicate_scan_result(self, result: ScanResult) -> None:
        self._clear_duplicate_results()
        self.duplicateReviewEmpty.hide()
        self.duplicateResultsSummary.setText(
            f"{len(result.groups):,} candidate groups from "
            f"{result.total:,} photos · Method: "
            f"{self._duplicate_detector.display_name} ({result.detector_id}). "
            "These are findings to assess, not confirmed duplicates."
        )
        self.duplicateResultsSummary.show()
        self.duplicateExcludeEmptyCandidatesCheck.setEnabled(True)
        self.duplicateResultsScroll.show()
        for group in result.groups:
            self._duplicate_assessments[group.group_id] = {
                "source": None,
                "targets": set(),
                "ignored": False,
                "submitted": False,
                "outcomes": {},
                "keep_backup": False,
            }
        self._filter_duplicate_candidates()

    @staticmethod
    def _duplicate_group_is_confirmed_empty(group: CandidateGroup) -> bool:
        return all(
            member.iptc_readable and not member.iptc_tags for member in group.members
        )

    def _filter_duplicate_candidates(self) -> None:
        result = self._duplicate_scan_result
        if result is None:
            return
        exclude_empty = self.duplicateExcludeEmptyCandidatesCheck.isChecked()
        self._visible_duplicate_group_ids = [
            group.group_id
            for group in result.groups
            if not self._duplicate_assessments[group.group_id]["ignored"]
            and not self._duplicate_assessments[group.group_id]["submitted"]
            and not (exclude_empty and self._duplicate_group_is_confirmed_empty(group))
        ]
        self._render_duplicate_candidate_queue()
        self._render_duplicate_status_rows()
        if self._active_duplicate_group_id in self._visible_duplicate_group_ids:
            self._show_duplicate_candidate_group(self._active_duplicate_group_id)
        elif self._visible_duplicate_group_ids:
            self._show_duplicate_candidate_group(self._visible_duplicate_group_ids[0])
        elif result.groups and exclude_empty:
            self._show_no_active_duplicate_group(
                "No candidate groups match the current filter. "
                "Clear ‘Hide groups where no photo has tags’ to review all findings."
            )
        else:
            self._show_no_active_duplicate_group(
                "No duplicate candidate groups were found."
            )

    def _duplicate_group(self, group_id: str) -> CandidateGroup | None:
        result = self._duplicate_scan_result
        if result is None:
            return None
        return next(
            (group for group in result.groups if group.group_id == group_id), None
        )

    def _render_duplicate_candidate_queue(self) -> None:
        self._clear_layout(self.duplicateCandidateQueueLayout)
        self._duplicate_group_buttons.clear()
        for position, group_id in enumerate(self._visible_duplicate_group_ids, start=1):
            group = self._duplicate_group(group_id)
            if group is None:
                continue
            timestamp = group.members[0].timestamp if group.members else "Unknown time"
            tagged = sum(
                bool(member.iptc_readable and member.iptc_tags)
                for member in group.members
            )
            button = QtWidgets.QPushButton(
                f"Candidate {position}\n{timestamp}\n"
                f"{len(group.members)} photos · {tagged} with tags"
            )
            button.setCheckable(True)
            button.setMinimumWidth(190)
            button.setAccessibleName(f"Open candidate group {position}")
            button.setToolTip(
                "Open candidate group (h/l in Edit mode or Left/Right in queue)"
            )
            button.setProperty("duplicateGroupId", group_id)
            button.installEventFilter(self)
            button.clicked.connect(
                lambda _checked=False, selected=group_id: (
                    self._show_duplicate_candidate_group(selected)
                )
            )
            self.duplicateCandidateQueueLayout.addWidget(button)
            self._duplicate_group_buttons[group_id] = button
        self.duplicateCandidateQueueLayout.addStretch(1)
        self.duplicateCandidateQueue.setVisible(bool(self._visible_duplicate_group_ids))

    def _show_duplicate_candidate_group(self, group_id: str) -> None:
        group = self._duplicate_group(group_id)
        if group is None:
            return
        assessment = self._duplicate_assessments[group_id]
        if assessment["submitted"]:
            self._show_duplicate_outcomes(group_id)
            return
        if group_id not in self._visible_duplicate_group_ids:
            return
        self._invalidate_duplicate_copy()
        self._duplicate_preview_generation += 1
        generation = self._duplicate_preview_generation
        self._active_duplicate_group_id = group_id
        for candidate_id, button in self._duplicate_group_buttons.items():
            button.setChecked(candidate_id == group_id)
        self._clear_layout(self.duplicateResultsLayout)
        self._duplicate_member_controls.clear()

        position = self._visible_duplicate_group_ids.index(group_id) + 1
        heading = QtWidgets.QLabel(
            f"Candidate group {position} of {len(self._visible_duplicate_group_ids)}"
        )
        heading_font = heading.font()
        heading_font.setPointSize(heading_font.pointSize() + 2)
        heading_font.setBold(True)
        heading.setFont(heading_font)
        self.duplicateResultsLayout.addWidget(heading)

        explanation = QtWidgets.QLabel(
            "These photos share capture-time evidence. Compare their previews and "
            "confirmed IPTC tags, then choose a tagged source and empty targets. "
            "Preview and confirm the tag copy—or ignore this candidate for this scan."
        )
        explanation.setWordWrap(True)
        explanation.setStyleSheet(
            "padding: 8px; border-left: 3px solid palette(highlight);"
        )
        self.duplicateResultsLayout.addWidget(explanation)

        timestamp = group.members[0].timestamp if group.members else "Unknown"
        fields = ", ".join(
            dict.fromkeys(member.source_field for member in group.members)
        )
        evidence = QtWidgets.QLabel(
            f"Evidence: exact effective capture timestamp {timestamp} · "
            f"field provenance: {fields} · method: "
            f"{self._duplicate_detector.display_name}"
        )
        evidence.setWordWrap(True)
        self.duplicateResultsLayout.addWidget(evidence)

        cards = QtWidgets.QWidget()
        cards_layout = QtWidgets.QGridLayout(cards)
        cards_layout.setContentsMargins(0, 4, 0, 4)
        controls: dict[str, tuple[QtWidgets.QRadioButton, QtWidgets.QCheckBox]] = {}
        tagged_members = [
            member
            for member in group.members
            if member.iptc_readable and member.iptc_tags
        ]
        suggested_path = tagged_members[0].path if len(tagged_members) == 1 else None
        assessment = self._duplicate_assessments[group_id]
        for index, member in enumerate(group.members):
            card = QtWidgets.QFrame()
            card.setFrameShape(QtWidgets.QFrame.Shape.StyledPanel)
            card.setProperty("duplicateMemberPath", member.path)
            card.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)
            card.installEventFilter(self)
            card.setMinimumWidth(210)
            card_layout = QtWidgets.QVBoxLayout(card)
            preview = QtWidgets.QLabel("Loading preview…")
            preview.setObjectName("duplicateCandidatePreview")
            preview.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            preview.setMinimumSize(190, 150)
            preview.setStyleSheet("background: palette(base); color: palette(mid);")
            card_layout.addWidget(preview, 1)
            self._load_duplicate_candidate_preview(member.path, preview, generation)

            name = QtWidgets.QLabel(Path(member.path).name)
            name.setWordWrap(True)
            name_font = name.font()
            name_font.setBold(True)
            name.setFont(name_font)
            name.setToolTip(member.path)
            card_layout.addWidget(name)
            path_label = QtWidgets.QLabel(member.path)
            path_label.setWordWrap(True)
            path_label.setStyleSheet("color: palette(mid);")
            card_layout.addWidget(path_label)
            provenance = QtWidgets.QLabel(
                f"{member.timestamp} via {member.source_field}"
            )
            provenance.setWordWrap(True)
            card_layout.addWidget(provenance)

            if not member.iptc_readable:
                tag_text = "Tags unknown — IPTC:Keywords could not be read"
            elif member.iptc_tags:
                tag_text = "Available tags: " + ", ".join(member.iptc_tags)
            else:
                tag_text = "Available tags: none (confirmed empty)"
            if member.path == suggested_path:
                tag_text += " · suggested source"
            tags = QtWidgets.QLabel(tag_text)
            tags.setWordWrap(True)
            card_layout.addWidget(tags)

            choices = QtWidgets.QHBoxLayout()
            source = QtWidgets.QRadioButton("Source (s)")
            source.setAutoExclusive(False)
            source.setAccessibleName(f"Use {member.path} as source")
            source.setToolTip("Use this photo as the tag source (s)")
            source.setEnabled(
                self._duplicate_member_eligible(group_id, member.path, source=True)
            )
            target = QtWidgets.QCheckBox("Target (t)")
            target.setEnabled(
                self._duplicate_member_eligible(group_id, member.path, source=False)
            )
            target.setAccessibleName(f"Use {member.path} as target")
            target.setToolTip("Include this photo as a tag target (t)")
            source.toggled.connect(
                lambda checked, selected_group=group_id, path=member.path: (
                    self._toggle_duplicate_source(selected_group, path, checked)
                )
            )
            target.toggled.connect(
                lambda checked, selected_group=group_id, path=member.path: (
                    self._set_duplicate_target(selected_group, path, checked)
                )
            )
            source.installEventFilter(self)
            target.installEventFilter(self)
            choices.addWidget(source)
            choices.addWidget(target)
            choices.addStretch(1)
            card_layout.addLayout(choices)
            controls[member.path] = (source, target)
            cards_layout.addWidget(card, index // 3, index % 3)

        self._duplicate_member_controls[group_id] = controls
        source_path = assessment["source"]
        targets = assessment["targets"]
        if source_path is not None:
            self._set_duplicate_source(group_id, str(source_path))
        for path in targets:
            if path in controls:
                controls[path][1].setChecked(True)
        self.duplicateResultsLayout.addWidget(cards)
        self._add_duplicate_read_failures()
        self.duplicateResultsLayout.addStretch(1)
        self.duplicateAssessmentActions.show()
        self._refresh_duplicate_assessment_hint()

    def _load_duplicate_candidate_preview(
        self, path: str, label: QtWidgets.QLabel, generation: int
    ) -> None:
        def load_image(photo_path: str) -> QtGui.QImage:
            reader = QtGui.QImageReader(photo_path)
            reader.setAutoTransform(True)
            image = reader.read()
            if image.isNull():
                raise RuntimeError("Preview unavailable")
            return image.scaled(
                480,
                320,
                QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                QtCore.Qt.TransformationMode.SmoothTransformation,
            )

        worker = Worker(load_image, path)
        self._duplicate_preview_workers.add(worker)

        def forget_worker() -> None:
            self._duplicate_preview_workers.discard(worker)

        def loaded(image: QtGui.QImage) -> None:
            forget_worker()
            if generation != self._duplicate_preview_generation:
                return
            pixmap = QtGui.QPixmap.fromImage(image)
            label.setPixmap(
                pixmap.scaled(
                    label.size(),
                    QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                    QtCore.Qt.TransformationMode.SmoothTransformation,
                )
            )
            label.setText("")

        def failed(_message: str) -> None:
            forget_worker()
            if generation == self._duplicate_preview_generation:
                label.setText("Preview unavailable")

        worker.signals.finished.connect(loaded)
        worker.signals.error.connect(failed)
        self.pool.start(worker)

    def _add_duplicate_read_failures(self) -> None:
        result = self._duplicate_scan_result
        if result is None or not result.errors:
            return
        failures = QtWidgets.QGroupBox(
            f"Other metadata read failures ({len(result.errors)})"
        )
        failures_layout = QtWidgets.QVBoxLayout(failures)
        for error in result.errors:
            label = QtWidgets.QLabel(f"{error.path} — {error.message}")
            label.setWordWrap(True)
            failures_layout.addWidget(label)
        self.duplicateResultsLayout.addWidget(failures)

    def _show_no_active_duplicate_group(self, message: str) -> None:
        self._invalidate_duplicate_copy()
        self._duplicate_preview_generation += 1
        self._active_duplicate_group_id = None
        self._duplicate_member_controls.clear()
        self._clear_layout(self.duplicateResultsLayout)
        label = QtWidgets.QLabel(message)
        label.setWordWrap(True)
        label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.duplicateResultsLayout.addStretch(1)
        self.duplicateResultsLayout.addWidget(label)
        self._add_duplicate_read_failures()
        self.duplicateResultsLayout.addStretch(1)
        self.duplicateAssessmentActions.hide()

    def focus_duplicate_scope(self) -> None:
        self.duplicateScopeCombo.setFocus()

    def _move_duplicate_group(self, delta: int) -> None:
        if not self._visible_duplicate_group_ids:
            return
        group_id = self._active_duplicate_group_id
        if group_id not in self._visible_duplicate_group_ids:
            next_index = 0
        else:
            current = self._visible_duplicate_group_ids.index(group_id)
            next_index = max(
                0, min(current + delta, len(self._visible_duplicate_group_ids) - 1)
            )
        next_group_id = self._visible_duplicate_group_ids[next_index]
        self._show_duplicate_candidate_group(next_group_id)
        button = self._duplicate_group_buttons.get(next_group_id)
        if button is not None:
            button.setFocus()

    def show_previous_duplicate_group(self) -> None:
        self._move_duplicate_group(-1)

    def show_next_duplicate_group(self) -> None:
        self._move_duplicate_group(1)

    def toggle_empty_duplicate_groups(self) -> None:
        if self.duplicateExcludeEmptyCandidatesCheck.isEnabled():
            self.duplicateExcludeEmptyCandidatesCheck.toggle()

    def _focused_duplicate_member_path(self) -> str | None:
        group_id = self._active_duplicate_group_id
        controls = self._duplicate_member_controls.get(group_id or "", {})
        focus = self.focusWidget()
        if focus is not None and focus.property("duplicateMemberPath") in controls:
            return str(focus.property("duplicateMemberPath"))
        for path, member_controls in controls.items():
            if focus in member_controls:
                return path
        group = self._duplicate_group(group_id or "")
        if group is None:
            return None
        return next(
            (member.path for member in group.members if member.path in controls),
            None,
        )

    def _focus_duplicate_member(self, delta: int) -> None:
        group_id = self._active_duplicate_group_id
        group = self._duplicate_group(group_id or "")
        controls = self._duplicate_member_controls.get(group_id or "", {})
        if group is None or not controls:
            return
        paths = [member.path for member in group.members if member.path in controls]
        current_path = self._focused_duplicate_member_path()
        focus = self.focusWidget()
        if focus not in {
            control for pair in controls.values() for control in pair
        } and (focus is None or focus.property("duplicateMemberPath") not in controls):
            next_index = 0
        else:
            current = paths.index(current_path) if current_path in paths else 0
            next_index = max(0, min(current + delta, len(paths) - 1))
        path = paths[next_index]
        source, target = controls[path]
        if source.isEnabled():
            source.setFocus()
        elif target.isEnabled():
            target.setFocus()
        else:
            for card in self.duplicateResultsBody.findChildren(QtWidgets.QFrame):
                if card.property("duplicateMemberPath") == path:
                    card.setFocus()
                    break

    def focus_previous_duplicate_member(self) -> None:
        self._focus_duplicate_member(-1)

    def focus_next_duplicate_member(self) -> None:
        self._focus_duplicate_member(1)

    def set_focused_duplicate_source(self) -> None:
        group_id = self._active_duplicate_group_id
        path = self._focused_duplicate_member_path()
        if group_id is not None and path is not None:
            self._set_duplicate_source(group_id, path)
            source = self._duplicate_member_controls[group_id][path][0]
            if source.isEnabled():
                source.setFocus()

    def toggle_focused_duplicate_target(self) -> None:
        group_id = self._active_duplicate_group_id
        path = self._focused_duplicate_member_path()
        if group_id is None or path is None:
            return
        target = self._duplicate_member_controls[group_id][path][1]
        if target.isEnabled():
            target.toggle()
            target.setFocus()

    def ignore_active_duplicate_group(self) -> None:
        group_id = self._active_duplicate_group_id
        if group_id is None or group_id not in self._visible_duplicate_group_ids:
            return
        self._invalidate_duplicate_copy()
        self._duplicate_assessments[group_id]["ignored"] = True
        self._advance_duplicate_review(group_id)
        self.statusBar().showMessage(
            "Candidate ignored for this scan; the decision was not saved"
        )

    def toggle_duplicate_edit_mode(self) -> None:
        self._duplicate_edit_mode = not self._duplicate_edit_mode
        self.duplicateEditModeButton.setText(
            "Edit mode: on (Esc)" if self._duplicate_edit_mode else "Edit mode: off (e)"
        )
        if self._active_duplicate_group_id in self._visible_duplicate_group_ids:
            self._refresh_duplicate_assessment_hint()

    def _duplicate_edit_key_handler(
        self, event: QtGui.QKeyEvent
    ) -> Callable[[], None] | None:
        if self.mainViews.currentWidget() is not self.duplicateReviewView:
            return None
        focus = self.focusWidget()
        if (
            isinstance(
                focus,
                (QtWidgets.QLineEdit, QtWidgets.QTextEdit, QtWidgets.QPlainTextEdit),
            )
            or event.modifiers() != QtCore.Qt.KeyboardModifier.NoModifier
        ):
            return None
        if event.key() == QtCore.Qt.Key.Key_E:
            return self.toggle_duplicate_edit_mode
        if not self._duplicate_edit_mode:
            return None
        if (
            event.key() == QtCore.Qt.Key.Key_Escape
            and self._active_duplicate_scan_id is not None
        ):
            return self.cancel_duplicate_scan
        handlers: dict[int, Callable[[], None]] = {
            QtCore.Qt.Key.Key_H: self.show_previous_duplicate_group,
            QtCore.Qt.Key.Key_L: self.show_next_duplicate_group,
            QtCore.Qt.Key.Key_J: self.focus_next_duplicate_member,
            QtCore.Qt.Key.Key_K: self.focus_previous_duplicate_member,
            QtCore.Qt.Key.Key_S: self.set_focused_duplicate_source,
            QtCore.Qt.Key.Key_T: self.toggle_focused_duplicate_target,
            QtCore.Qt.Key.Key_C: self.preview_duplicate_copy,
            QtCore.Qt.Key.Key_I: self.ignore_active_duplicate_group,
            QtCore.Qt.Key.Key_Escape: self.toggle_duplicate_edit_mode,
        }
        return handlers.get(event.key())

    def _handle_duplicate_key_event(self, event: QtCore.QEvent) -> bool:
        if not isinstance(event, QtGui.QKeyEvent) or event.type() not in (
            QtCore.QEvent.Type.ShortcutOverride,
            QtCore.QEvent.Type.KeyPress,
        ):
            return False
        handler = self._duplicate_edit_key_handler(event)
        if handler is None:
            return False
        if event.type() == QtCore.QEvent.Type.KeyPress:
            handler()
        event.accept()
        return True

    def _duplicate_status_message(self, message: str) -> None:
        status_bar = self.statusBar()
        assert status_bar is not None
        status_bar.showMessage(message)

    def _invalidate_duplicate_copy(self) -> None:
        self._duplicate_copy_generation += 1
        if self._duplicate_copy_preview is not None:
            self._duplicate_copy_preview.reject()
            self._duplicate_copy_preview = None

    def preview_duplicate_copy(self) -> None:
        result = self._duplicate_scan_result
        group_id = self._active_duplicate_group_id
        if result is None or group_id is None:
            return
        assessment = self._duplicate_assessments[group_id]
        source = assessment["source"]
        if source is None or not assessment["targets"]:
            return
        self._invalidate_duplicate_copy()
        generation = self._duplicate_copy_generation
        targets = tuple(sorted(assessment["targets"]))
        keep_backup = self.keepBackup.isChecked()
        statuses = {
            path: self._tag_mutation_coordinator.status_for(path)
            for path in (source, *targets)
        }
        self.duplicateApplyTagsButton.setEnabled(False)
        self._duplicate_status_message("Refreshing source and target tags…")
        worker = Worker(
            prepare_propagation,
            result,
            group_id,
            source,
            targets,
            keep_backup,
            self.exif.read_keywords,
            statuses.get,
        )
        self._duplicate_copy_workers.add(worker)

        def ready(plan: TagPropagationPlan) -> None:
            self._duplicate_copy_workers.discard(worker)
            if (
                generation != self._duplicate_copy_generation
                or result is not self._duplicate_scan_result
            ):
                return
            if any(
                self._tag_mutation_coordinator.status_for(path)
                is MutationStatus.PENDING
                for path in (plan.source, *plan.targets)
            ):
                failed("Pending tag changes must settle before copying")
                return
            self._refresh_duplicate_assessment_hint()
            dialog = DuplicateCopyPreview(plan, self)
            self._duplicate_copy_preview = dialog
            dialog.accepted.connect(
                lambda: self._confirm_duplicate_copy(plan, result, generation)
            )
            dialog.finished.connect(
                lambda _result: setattr(self, "_duplicate_copy_preview", None)
            )
            dialog.finished.connect(dialog.deleteLater)
            dialog.open()

        def failed(message: str) -> None:
            self._duplicate_copy_workers.discard(worker)
            if generation == self._duplicate_copy_generation:
                self._refresh_duplicate_assessment_hint()
                self._duplicate_status_message(message)

        worker.signals.finished.connect(ready)
        worker.signals.error.connect(failed)
        assert self.pool is not None
        self.pool.start(worker)

    def _confirm_duplicate_copy(
        self, plan: TagPropagationPlan, result: ScanResult, generation: int
    ) -> None:
        if (
            generation != self._duplicate_copy_generation
            or result is not self._duplicate_scan_result
        ):
            return
        statuses = {
            path: self._tag_mutation_coordinator.status_for(path)
            for path in (plan.source, *plan.targets)
        }
        self.duplicateApplyTagsButton.setEnabled(False)
        worker = Worker(
            validate_propagation, plan, result, self.exif.read_keywords, statuses.get
        )
        self._duplicate_copy_workers.add(worker)

        def ready(states: dict[str, KeywordState]) -> None:
            self._duplicate_copy_workers.discard(worker)
            if (
                generation != self._duplicate_copy_generation
                or result is not self._duplicate_scan_result
            ):
                return
            if any(
                self._tag_mutation_coordinator.status_for(path)
                is MutationStatus.PENDING
                for path in states
            ):
                failed("Pending tag changes must settle before copying")
                return
            self._tag_mutation_coordinator.remember_confirmed(states)
            assessment = self._duplicate_assessments[plan.group_id]
            assessment["submitted"] = True
            assessment["keep_backup"] = plan.keep_backup
            assessment["outcomes"] = {path: "pending" for path in plan.targets}
            mutation = self._tag_mutation_coordinator.begin_intents(
                {
                    path: [TagIntent.add(tag) for tag in plan.tags]
                    for path in plan.targets
                },
                states,
            )
            if mutation is None:
                return
            self._duplicate_mutations[mutation.sequence] = (result, plan.group_id)
            self._advance_duplicate_review(plan.group_id)

            def copy(paths: list[str]) -> TagMutationResult:
                source = self.exif.read_keywords(plan.source)
                if not source.iptc_readable or tuple(source.iptc) != plan.tags:
                    raise ValueError("Source tags changed after confirmation")

                def exact_copy(_path: str, state: KeywordState) -> list[str]:
                    require_empty_target(state)
                    return list(plan.tags)

                return self.tag_mutations.replace_keywords(
                    paths, plan.keep_backup, self.exif.read_keywords, exact_copy
                )

            self._enqueue_tag_mutation(
                list(plan.targets), copy, mutation, "Tag copy completed"
            )

        def failed(message: str) -> None:
            self._duplicate_copy_workers.discard(worker)
            if generation == self._duplicate_copy_generation:
                self._refresh_duplicate_assessment_hint()
                self._duplicate_status_message(message)

        worker.signals.finished.connect(ready)
        worker.signals.error.connect(failed)
        assert self.pool is not None
        self.pool.start(worker)

    def _advance_duplicate_review(self, group_id: str) -> None:
        index = (
            self._visible_duplicate_group_ids.index(group_id)
            if group_id in self._visible_duplicate_group_ids
            else 0
        )
        self._visible_duplicate_group_ids = [
            candidate
            for candidate in self._visible_duplicate_group_ids
            if candidate != group_id
        ]
        self._render_duplicate_candidate_queue()
        self._render_duplicate_status_rows()
        if self._visible_duplicate_group_ids:
            self._show_duplicate_candidate_group(
                self._visible_duplicate_group_ids[
                    min(index, len(self._visible_duplicate_group_ids) - 1)
                ]
            )
        else:
            self._show_no_active_duplicate_group(
                "Review complete. Reopen a status row to inspect outcomes or restore an ignored candidate."
            )

    def _render_duplicate_status_rows(self) -> None:
        self._clear_layout(self.duplicateStatusRowsLayout)
        for group_id, assessment in self._duplicate_assessments.items():
            if not assessment["ignored"] and not assessment["submitted"]:
                continue
            outcomes = assessment["outcomes"]
            pending = sum(value == "pending" for value in outcomes.values())
            failed = sum(value == "failed" for value in outcomes.values())
            successful = sum(value == "successful" for value in outcomes.values())
            cancelled = sum(value == "cancelled" for value in outcomes.values())
            status = (
                "Ignored"
                if assessment["ignored"]
                else "Pending"
                if pending
                else "Failed"
                if failed
                else "Cancelled"
                if cancelled
                else "Completed"
            )
            row = QtWidgets.QWidget()
            layout = QtWidgets.QHBoxLayout(row)
            layout.setContentsMargins(0, 0, 0, 0)
            button = QtWidgets.QPushButton(
                f"{status} · {group_id[:8]} · {successful} successful / {failed} failed / {pending} pending — reopen"
            )
            if failed:
                button.setStyleSheet("font-weight: bold; border: 2px solid #dc2626;")
            button.clicked.connect(
                lambda _checked=False, selected=group_id: self._reopen_duplicate_status(
                    selected
                )
            )
            layout.addWidget(button, 1)
            if pending:
                spinner = QtWidgets.QProgressBar()
                spinner.setRange(0, 0)
                spinner.setMaximumWidth(100)
                layout.addWidget(spinner)
            self.duplicateStatusRowsLayout.addWidget(row)
        self.duplicateStatusRowsScroll.setVisible(
            self.duplicateStatusRowsLayout.count() > 0
        )

    def _reopen_duplicate_status(self, group_id: str) -> None:
        assessment = self._duplicate_assessments[group_id]
        if assessment["ignored"]:
            assessment["ignored"] = False
            self._active_duplicate_group_id = group_id
            self._filter_duplicate_candidates()
        else:
            self._show_duplicate_outcomes(group_id)

    def _show_duplicate_outcomes(self, group_id: str) -> None:
        self._invalidate_duplicate_copy()
        self._duplicate_preview_generation += 1
        self._active_duplicate_group_id = group_id
        self._duplicate_member_controls.clear()
        self._clear_layout(self.duplicateResultsLayout)
        assessment = self._duplicate_assessments[group_id]
        for path, outcome in assessment["outcomes"].items():
            label = QtWidgets.QLabel(f"{path}: {outcome}")
            label.setWordWrap(True)
            self.duplicateResultsLayout.addWidget(label)
        retry = QtWidgets.QPushButton("Retry failed targets")
        retry.setEnabled(
            any(value == "failed" for value in assessment["outcomes"].values())
            and not any(value == "pending" for value in assessment["outcomes"].values())
        )
        retry.clicked.connect(lambda: self.retry_duplicate_copy(group_id))
        self.duplicateResultsLayout.addWidget(retry)
        self.duplicateResultsLayout.addStretch(1)
        self.duplicateAssessmentActions.hide()

    def retry_duplicate_copy(self, group_id: str) -> None:
        result = self._duplicate_scan_result
        if result is None:
            return
        assessment = self._duplicate_assessments[group_id]
        failed = [
            path
            for path, outcome in assessment["outcomes"].items()
            if outcome == "failed"
        ]
        retry = self._tag_mutation_coordinator.retry_failed(failed)
        if retry is None:
            self._duplicate_status_message("No failed tag intent remains to retry")
            return
        self._duplicate_mutations[retry.sequence] = (result, group_id)
        paths = list(retry.intents_by_path)
        assessment["outcomes"].update({path: "pending" for path in paths})
        keep_backup = assessment["keep_backup"]
        self._render_duplicate_status_rows()
        self._show_duplicate_outcomes(group_id)

        def retry_empty_target(path: str, state: KeywordState) -> KeywordState:
            require_empty_target(state)
            return retry.apply(path, state)

        self._enqueue_tag_mutation(
            paths,
            lambda paths: self.tag_mutations.replace_keyword_states(
                paths,
                keep_backup=keep_backup,
                load_state=self.exif.read_keywords,
                transform=retry_empty_target,
            ),
            retry,
            "Retried failed copy targets",
        )

    def _handle_duplicate_mutation_lifecycle(self, event: TagMutationLifecycle) -> None:
        if event.mutation is None:
            return
        tracked = self._duplicate_mutations.get(event.mutation.sequence)
        if tracked is None:
            return
        result, group_id = tracked
        if result is not self._duplicate_scan_result:
            if event.kind is not TagMutationLifecycleKind.PENDING:
                self._duplicate_mutations.pop(event.mutation.sequence, None)
            return
        assessment = self._duplicate_assessments[group_id]
        if event.kind is TagMutationLifecycleKind.COMPLETED:
            assessment["outcomes"].update(
                {path: "successful" for path, _state in event.confirmed_states}
            )
            assessment["outcomes"].update(
                {path: "failed" for path in event.failed_paths}
            )
        elif event.kind is TagMutationLifecycleKind.FAILED:
            assessment["outcomes"].update(
                {path: "failed" for path, _state in event.restored_states}
            )
        elif event.kind is TagMutationLifecycleKind.DISCARDED:
            assessment["outcomes"].update(
                {path: "cancelled" for path in event.discarded_paths}
            )
        if not any(value == "pending" for value in assessment["outcomes"].values()):
            self._duplicate_mutations.pop(event.mutation.sequence, None)
        self._render_duplicate_status_rows()
        if self._active_duplicate_group_id == group_id:
            self._show_duplicate_outcomes(group_id)

    def _refresh_duplicate_assessment_hint(self) -> None:
        group_id = self._active_duplicate_group_id
        if group_id is None:
            return
        assessment = self._duplicate_assessments[group_id]
        source = assessment["source"]
        target_count = len(assessment["targets"])
        ready = source is not None and bool(target_count)
        self.duplicateApplyTagsButton.setEnabled(ready)
        self.duplicateAssessmentHint.setText(
            (
                f"Ready: 1 source, {target_count} target(s). "
                if ready
                else "Choose a tagged source and empty targets. "
            )
            + (
                "Edit: h/l groups · j/k photos · s source · t target · c preview · i ignore · Esc leave Edit"
                if self._duplicate_edit_mode
                else "e enters Edit mode; mouse controls remain available."
            )
        )

    def _duplicate_member_eligible(
        self, group_id: str, path: str, *, source: bool
    ) -> bool:
        group = self._duplicate_group(group_id)
        member = (
            next((member for member in group.members if member.path == path), None)
            if group
            else None
        )
        return bool(
            member
            and member.iptc_readable
            and bool(member.iptc_tags) == source
            and self._tag_mutation_coordinator.status_for(path)
            is not MutationStatus.PENDING
        )

    def _toggle_duplicate_source(self, group_id: str, path: str, checked: bool) -> None:
        assessment = self._duplicate_assessments[group_id]
        if not checked:
            if assessment["source"] == path:
                source = self._duplicate_member_controls[group_id][path][0]
                source.blockSignals(True)
                source.setChecked(True)
                source.blockSignals(False)
            return
        self._set_duplicate_source(group_id, path)

    def _set_duplicate_source(self, group_id: str, path: str) -> None:
        assessment = self._duplicate_assessments[group_id]
        if not self._duplicate_member_eligible(group_id, path, source=True):
            return
        self._invalidate_duplicate_copy()
        changed_source = assessment["source"] != path
        assessment["source"] = path
        targets = assessment["targets"]
        if changed_source:
            targets.clear()
            group = self._duplicate_group(group_id)
            if group:
                targets.update(
                    member.path
                    for member in group.members
                    if self._duplicate_member_eligible(
                        group_id, member.path, source=False
                    )
                )
        controls = self._duplicate_member_controls[group_id]
        for member_path, (source, target) in controls.items():
            should_check = member_path == path
            if source.isChecked() != should_check:
                source.blockSignals(True)
                source.setChecked(should_check)
                source.blockSignals(False)
            target.setEnabled(
                self._duplicate_member_eligible(group_id, member_path, source=False)
            )
            target.blockSignals(True)
            target.setChecked(member_path in targets)
            target.blockSignals(False)
        self._refresh_duplicate_assessment_hint()

    def _set_duplicate_target(self, group_id: str, path: str, checked: bool) -> None:
        self._invalidate_duplicate_copy()
        assessment = self._duplicate_assessments[group_id]
        targets = assessment["targets"]
        if checked:
            if assessment["source"] == path or not self._duplicate_member_eligible(
                group_id, path, source=False
            ):
                control = self._duplicate_member_controls[group_id][path][1]
                control.blockSignals(True)
                control.setChecked(False)
                control.blockSignals(False)
                return
            targets.add(path)
        else:
            targets.discard(path)
        self._refresh_duplicate_assessment_hint()

    def show_duplicate_review(self) -> None:
        focus = self.focusWidget()
        if focus is not None and self.taggingWorkspaceView.isAncestorOf(focus):
            self._tagging_focus_widget = focus
        self.mainViews.setCurrentWidget(self.duplicateReviewView)
        self.duplicateReviewAction.setChecked(True)
        self.viewSelector.setAccessibleName(
            "Current application view: Duplicate review"
        )
        self._refresh_duplicate_scope_controls()
        self._ensure_duplicate_scope_prepared()
        self.duplicateReviewBackButton.setFocus()

    def show_tagging_workspace(self) -> None:
        self._invalidate_duplicate_copy()
        if self._duplicate_edit_mode:
            self.toggle_duplicate_edit_mode()
        self.mainViews.setCurrentWidget(self.taggingWorkspaceView)
        self.taggingViewAction.setChecked(True)
        self.viewSelector.setAccessibleName("Current application view: Tagging")
        focus = self._tagging_focus_widget
        if focus is not None and focus.isEnabled():
            focus.setFocus()
        else:
            self.files.setFocus()

    def _init_actions(self) -> None:
        specs = build_action_specs()
        self._actions_by_id = {spec.id: spec for spec in specs}
        self._listed_actions = [
            spec for spec in specs if spec.command is not None and spec.show_in_help
        ]
        self._widget_refs = self._build_widget_refs()
        self._commands_by_name = {}
        self._install_shortcuts_from_actions()
        self._index_commands_from_actions()

    def _build_widget_refs(self) -> dict[str, QtCore.QObject]:
        return {
            "window": self,
            "files": self.files,
            "keywordsList": self.keywordsList,
            "addEdit": self.addEdit,
            "dbDateSearchEdit": self.dbDateSearchEdit,
            "filenameFilterEdit": self.filenameFilterEdit,
            "directoryExcludeEdit": self.directoryExcludeEdit,
            "filesFilterBox": self.filesFilterBox,
            "filesFilterToggleBtn": self.filesFilterToggleBtn,
            "duplicateReviewView": self.duplicateReviewView,
            "cmdLine": self.cmdLine,
        }

    def _index_root_for_paths(self, paths: list[str]) -> str | None:
        # An empty database-search result has no paths of its own. Keep its
        # originating root rather than treating the configured default as a new
        # root for the next query.
        if not paths:
            return self._index_root
        root = resolve_index_root(paths, preferred_root=DEFAULT_INDEX_ROOT)
        return str(root) if root is not None else self._index_root

    def _schedule_index_sync(
        self,
        root: str | None,
        paths: list[str],
        *,
        paths_are_normalized: bool = False,
    ) -> None:
        if not root:
            return
        root = normalize_path(root)
        if root in self._index_sync_inflight:
            return
        self._index_sync_inflight.add(root)
        self._index_root = root
        self.statusBar().showMessage("Indexing photos…")
        self._background_coordinator.ensure_index(
            root, paths, paths_are_normalized=paths_are_normalized
        )

    def _update_index_states(self, states: dict[str, KeywordState]) -> None:
        if not states:
            return
        root = self._index_root_for_paths(list(states.keys()))
        if root:
            self._background_coordinator.submit_confirmed_states(root, states)

    def _index_missing_paths(self, root: str, paths: list[str]) -> None:
        self._background_coordinator.index_missing_paths(root, paths)

    def _install_shortcuts_from_actions(self) -> None:
        self._shortcuts = []
        for spec in self._actions_by_id.values():
            for binding in spec.shortcuts:
                widget = self._widget_refs.get(binding.widget_ref)
                if widget is None:
                    continue
                shortcut = QtGui.QShortcut(QtGui.QKeySequence(binding.sequence), widget)
                shortcut.setContext(binding.context)
                shortcut.activated.connect(
                    lambda action_id=spec.id: self._dispatch_action(action_id)
                )
                self._shortcuts.append(shortcut)

    def _index_commands_from_actions(self) -> None:
        for spec in self._listed_actions:
            command = spec.command
            if command is None:
                continue
            self._commands_by_name[command.name] = spec
            for alias in command.aliases:
                self._commands_by_name[alias] = spec

    def _dispatch_action(
        self, action_id: str, *, command_args: list[str] | None = None
    ) -> None:
        spec = self._actions_by_id.get(action_id)
        if spec is None:
            raise RuntimeError(f"Unknown action: {action_id}")
        allowed_in_duplicate_review = {
            "addfolder",
            "cancelduplicates",
            "focusduplicatescope",
            "ignoreduplicate",
            "nextduplicategroup",
            "nextduplicatemember",
            "previousduplicategroup",
            "previousduplicatemember",
            "scanduplicates",
            "setduplicatesource",
            "showduplicates",
            "showtagging",
            "toggleduplicatetarget",
            "toggleemptyduplicates",
            "open_command_line",
            "complete_command_line",
            "listcommands",
            "quit",
            "escape",
        }
        if (
            self.mainViews.currentWidget() is self.duplicateReviewView
            and action_id not in allowed_in_duplicate_review
        ):
            self.statusBar().showMessage(
                "Return to the tagging workspace to use tagging commands"
            )
            return
        accepts_arguments = spec.command is not None and spec.command.accepts_arguments
        handler = getattr(self, spec.handler_name, None)
        if not callable(handler):
            if accepts_arguments:
                raise RuntimeError(
                    f"Missing argument handler for action: {spec.id} "
                    f"({spec.handler_name})"
                )
            raise RuntimeError(  # noqa: TRY004 - invalid action wiring is not a type error
                f"Missing handler for action: {spec.id} ({spec.handler_name})"
            )
        if accepts_arguments:
            handler(command_args or [])
            return
        handler()

    def _dispatch_command(self, name: str, args: list[str]) -> None:
        spec = self._commands_by_name.get(name)
        if spec is None:
            self.statusBar().showMessage(f"Unknown command: {name}")
            return
        try:
            self._dispatch_action(spec.id, command_args=args)
        except Exception as e:  # noqa: BLE001 - command boundary reports handler failures
            self._show_error(str(e), source="Command")

    def _format_key_route_label(self, route: KeyRoute) -> str:
        if route.kind == "sequence":
            if len(route.sequence) == 2 and all(
                len(token) == 1 for token in route.sequence
            ):
                return "".join(route.sequence)
            if route.sequence[0] == "Space":
                return f"Space {route.sequence[1].upper()}"
            return "+".join(route.sequence)
        return route.sequence[0]

    def _action_help_labels(self, spec: ActionSpec) -> list[str]:
        labels: list[str] = []
        command = spec.command
        if command is not None and spec.id in {"listcommands", "quit"}:
            labels.append(f":{command.name}")
            labels.extend(f":{alias}" for alias in command.aliases)
        labels.extend(
            binding.sequence for binding in spec.shortcuts if binding.show_in_help
        )
        labels.extend(
            self._format_key_route_label(route)
            for route in spec.key_routes
            if route.show_in_help
        )
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
            'QLineEdit[keywordLengthInvalid="true"] '
            "{ border: 2px solid #dc2626; color: #dc2626; }"
        )
        for lst in (self.files, self.keywordsList):
            lst.setStyleSheet(list_qss)
        for edit in (
            self.addEdit,
            self.dbSearchEdit,
            self.dbDateSearchEdit,
            self.filenameFilterEdit,
            self.directoryExcludeEdit,
            self.cmdLine,
        ):
            edit.setStyleSheet(edit_qss)

    def eventFilter(self, obj: QtCore.QObject, event: QtCore.QEvent) -> bool:
        et = event.type()
        if self._handle_duplicate_key_event(event):
            return True
        if (
            et == QtCore.QEvent.Type.KeyPress
            and isinstance(obj, QtWidgets.QPushButton)
            and obj.property("duplicateGroupId") is not None
        ):
            key = event.key()
            if key == QtCore.Qt.Key.Key_Left:
                self.show_previous_duplicate_group()
                return True
            if key == QtCore.Qt.Key.Key_Right:
                self.show_next_duplicate_group()
                return True
        if obj is self.addEdit:
            if et in (QtCore.QEvent.Type.Move, QtCore.QEvent.Type.Resize):
                self._position_tag_hint()
            if self._tagHint.handle_event(event):
                return True
        if obj is self.previewLabel and et == QtCore.QEvent.Type.Resize:
            self._update_preview_pixmap()
        if obj is self.files.viewport() and et == QtCore.QEvent.Type.Resize:
            self._position_files_pane_message()
        if obj is self.files.viewport() and et == QtCore.QEvent.Type.MouseButtonPress:
            self._files_shift_selection_anchor = None
            self._capture_files_selection_scroll_anchor()
        if obj is self.files.viewport() and et == QtCore.QEvent.Type.MouseButtonRelease:
            self._schedule_files_selection_scroll_anchor_restore()
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
                self.handle_dropped_urls(event.mimeData().urls())
                event.acceptProposedAction()
                return True
        if obj is self.files.viewport() and et == QtCore.QEvent.Type.ContextMenu:
            context_event = event
            if isinstance(context_event, QtGui.QContextMenuEvent):
                self._show_file_context_menu(
                    context_event.pos(), context_event.modifiers()
                )
                return True
        if (
            et == QtCore.QEvent.Type.ShortcutOverride
            and isinstance(event, QtGui.QKeyEvent)
            and self._handle_shortcut_override(event)
        ):
            return True
        if (
            et == QtCore.QEvent.Type.KeyPress
            and isinstance(event, QtGui.QKeyEvent)
            and self._handle_key_routes(obj, event)
        ):
            return True
        return super().eventFilter(obj, event)

    def _list_from_obj(
        self, obj: QtCore.QObject | None
    ) -> QtWidgets.QListWidget | None:
        cur = obj
        while cur is not None:
            if cur in (self.files, self.keywordsList):
                return cur
            try:
                cur = cur.parent()
            except RuntimeError:
                break
        return None

    def _resolve_current_list_widget(
        self, obj: QtCore.QObject | None = None
    ) -> QtWidgets.QListWidget | None:
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
        if event.key() == QtCore.Qt.Key.Key_J and (
            event.modifiers() & QtCore.Qt.KeyboardModifier.ShiftModifier
        ):
            return "Shift+J"
        if event.key() == QtCore.Qt.Key.Key_K and (
            event.modifiers() & QtCore.Qt.KeyboardModifier.ShiftModifier
        ):
            return "Shift+K"
        if event.key() == QtCore.Qt.Key.Key_T and (
            event.modifiers() & QtCore.Qt.KeyboardModifier.ShiftModifier
        ):
            return "T"
        if event.key() == QtCore.Qt.Key.Key_Down and (
            event.modifiers() & QtCore.Qt.KeyboardModifier.ShiftModifier
        ):
            return "Shift+Down"
        if event.key() == QtCore.Qt.Key.Key_Up and (
            event.modifiers() & QtCore.Qt.KeyboardModifier.ShiftModifier
        ):
            return "Shift+Up"
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
            QtCore.Qt.Key.Key_J: (
                "Shift+J"
                if event.modifiers() & QtCore.Qt.KeyboardModifier.ShiftModifier
                else "j"
            ),
            QtCore.Qt.Key.Key_K: (
                "Shift+K"
                if event.modifiers() & QtCore.Qt.KeyboardModifier.ShiftModifier
                else "k"
            ),
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
                if route.scope != scope or route.kind not in (
                    "single",
                    "widget_specific",
                ):
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
            if (
                self._find_matching_single_route(
                    token, scope, self.focusWidget(), list_widget
                )
                is not None
            ):
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

        if prefix == "Space":
            if token == prefix:
                self._vim_space_pending = now
                if list_widget is self.files:
                    self._show_cmd_matches(
                        "Space O open · G GIMP · C copy path · R reveal · "
                        "Y yank tags · P paste tags"
                    )
                    QtCore.QTimer.singleShot(1_000, self._hide_cmd_matches)
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
                    self._hide_cmd_matches()
                    self._dispatch_action(action_id)
                    return True
                self._vim_space_pending = None
                return False
            if (
                self._vim_space_pending is not None
                and (now - self._vim_space_pending) > timeout_ms
            ):
                self._vim_space_pending = None
            return False

        return False

    def _handle_non_space_sequence_routes(
        self,
        token: str,
        obj: QtCore.QObject | None,
        list_widget: QtWidgets.QListWidget | None,
    ) -> bool:
        routes: list[tuple[str, KeyRoute]] = []
        for spec in self._actions_by_id.values():
            for route in spec.key_routes:
                if (
                    route.kind == "sequence"
                    and len(route.sequence) == 2
                    and route.sequence[0] != "Space"
                    and self._scope_matches(route, obj, list_widget)
                ):
                    routes.append((spec.id, route))

        now = int(QtCore.QDateTime.currentMSecsSinceEpoch())
        for prefix, started_at in tuple(self._vim_sequence_pending.items()):
            matching = [
                (action_id, route)
                for action_id, route in routes
                if route.sequence[0] == prefix
            ]
            timeout_ms = max(
                (route.timeout_ms or 600 for _action_id, route in matching),
                default=600,
            )
            self._vim_sequence_pending.pop(prefix, None)
            if now - started_at > timeout_ms:
                continue
            for action_id, route in matching:
                if token == route.sequence[1]:
                    self._dispatch_action(action_id)
                    return True

        prefixes = {route.sequence[0] for _action_id, route in routes}
        if token in prefixes:
            self._vim_sequence_pending[token] = now
            return True
        return False

    def _handle_key_routes(self, obj: QtCore.QObject, event: QtGui.QKeyEvent) -> bool:
        token = self._event_token(event)
        if token is None:
            return False

        focus = self.focusWidget()
        list_widget = self._resolve_current_list_widget(obj)
        accepts_vim_route = not isinstance(
            focus, QtWidgets.QLineEdit
        ) and self._mods_ok(event.modifiers())
        if not accepts_vim_route:
            self._vim_sequence_pending.clear()

        if accepts_vim_route:
            if self._vim_space_pending is not None:
                for spec in self._actions_by_id.values():
                    for route in spec.key_routes:
                        if (
                            route.scope == "list_widgets"
                            and route.sequence[0] == "Space"
                            and self._handle_prefix_route(
                                route, spec.id, token, obj, list_widget
                            )
                        ):
                            return True
            if self._handle_non_space_sequence_routes(token, obj, list_widget):
                return True
            for scope in ("global_non_input", "list_widgets"):
                match = self._find_matching_single_route(token, scope, obj, list_widget)
                if match is not None:
                    self._dispatch_action(match.id)
                    return True
                for spec in self._actions_by_id.values():
                    for route in spec.key_routes:
                        if (
                            route.scope == scope
                            and route.kind == "sequence"
                            and self._handle_prefix_route(
                                route, spec.id, token, obj, list_widget
                            )
                        ):
                            return True

        widget_match = self._find_matching_single_route(
            token, "widget_exact", obj, list_widget
        )
        if widget_match is not None:
            self._dispatch_action(widget_match.id)
            return True

        for spec in self._actions_by_id.values():
            for route in spec.key_routes:
                if (
                    route.scope == "widget_exact"
                    and route.kind == "sequence"
                    and self._handle_prefix_route(
                        route, spec.id, token, obj, list_widget
                    )
                ):
                    return True

        return False

    def _mods_ok(self, mods: QtCore.Qt.KeyboardModifier) -> bool:
        allowed = QtCore.Qt.KeyboardModifier.ShiftModifier
        return (mods & ~allowed) == QtCore.Qt.KeyboardModifier.NoModifier

    def _move_list_selection(
        self, lst: QtWidgets.QListWidget, delta: int, *, extend: bool = False
    ) -> None:
        if lst.count() == 0:
            return
        row = lst.currentRow()
        if row < 0:
            row = (
                self._first_visible_row(lst)
                if delta >= 0
                else self._last_visible_row(lst)
            )
        else:
            row = self._next_visible_row(lst, row, delta)
        if row is None:
            return
        if lst is self.files and extend:
            target_item = lst.item(row)
            if target_item is None:
                return
            target_was_visible = lst.visualItemRect(target_item).intersects(
                lst.viewport().rect()
            )
            scroll_anchor = (
                self._capture_files_scroll_anchor() if target_was_visible else None
            )
            if self._files_shift_selection_anchor is None:
                self._files_shift_selection_anchor = lst.currentRow()
            anchor = self._files_shift_selection_anchor
            visible_rows = self._visible_file_rows()
            anchor_index = visible_rows.index(anchor)
            row_index = visible_rows.index(row)
            low, high = sorted((anchor_index, row_index))
            lst.blockSignals(True)
            try:
                lst.clearSelection()
                for selected_row in visible_rows[low : high + 1]:
                    item = lst.item(selected_row)
                    if item is not None:
                        item.setSelected(True)
                lst.setCurrentItem(
                    target_item,
                    QtCore.QItemSelectionModel.SelectionFlag.NoUpdate,
                )
            finally:
                lst.blockSignals(False)
            self.on_selection_changed()
            if scroll_anchor is not None:
                self._queue_files_selection_scroll_anchor_restore(scroll_anchor)
            else:
                self._ensure_list_item_visible(lst, target_item)
        elif lst is self.keywordsList and self._vim_visual_keywords:
            self._select_list_range(lst, self._vim_visual_anchor, row)
            lst.setCurrentRow(row)
        else:
            if lst is self.files:
                self._files_shift_selection_anchor = None
            if lst is self.keywordsList:
                self._set_single_list_selection(lst, row)
            elif lst is self.files:
                self._set_file_current_row(row)
            else:
                lst.setCurrentRow(row)
        if lst is not self.files:
            self._ensure_list_item_visible(lst, lst.currentItem())

    def _go_list_edge(self, lst: QtWidgets.QListWidget, to_end: bool) -> None:
        if lst.count() == 0:
            return
        row = self._last_visible_row(lst) if to_end else self._first_visible_row(lst)
        if row is None:
            return
        if lst is self.keywordsList and not self._vim_visual_keywords:
            self._set_single_list_selection(lst, row)
        elif lst is self.files:
            self._set_file_current_row(row)
            return
        else:
            lst.setCurrentRow(row)
        self._ensure_list_item_visible(lst, lst.currentItem())

    def _set_file_current_row(self, row: int) -> None:
        """Change a Files-pane selection without Qt moving a visible target."""
        item = self.files.item(row)
        if item is None:
            return
        rect = self.files.visualItemRect(item)
        viewport = self.files.viewport().rect()
        was_visible = rect.intersects(viewport)
        anchor = self._capture_files_scroll_anchor() if was_visible else None
        self.files.setCurrentRow(
            row,
            QtCore.QItemSelectionModel.SelectionFlag.ClearAndSelect,
        )
        if anchor is not None:
            # Windows QListWidget can apply ensure-visible after setCurrentRow.
            self._queue_files_selection_scroll_anchor_restore(anchor)
            return
        self._ensure_list_item_visible(self.files, item)

    def _ensure_list_item_visible(
        self,
        lst: QtWidgets.QListWidget,
        item: QtWidgets.QListWidgetItem | None,
    ) -> None:
        """Scroll only when keyboard selection leaves the current viewport."""
        if item is None:
            return
        rect = lst.visualItemRect(item)
        viewport = lst.viewport().rect()
        if rect.top() < viewport.top():
            lst.scrollToItem(item, QtWidgets.QAbstractItemView.ScrollHint.PositionAtTop)
        elif rect.bottom() > viewport.bottom():
            lst.scrollToItem(
                item, QtWidgets.QAbstractItemView.ScrollHint.PositionAtBottom
            )

    def _visible_file_rows(self) -> tuple[int, ...]:
        """Return file-widget rows from the workspace's logical visibility."""
        snapshot = self.photo_workspace.snapshot()
        visible_paths = set(snapshot.visible_paths)
        return tuple(
            index for index, path in enumerate(snapshot.paths) if path in visible_paths
        )

    def _first_visible_row(self, lst: QtWidgets.QListWidget) -> int | None:
        if lst is self.files:
            rows = self._visible_file_rows()
            return rows[0] if rows else None
        for i in range(lst.count()):
            it = lst.item(i)
            if it is not None and not it.isHidden():
                return i
        return None

    def _last_visible_row(self, lst: QtWidgets.QListWidget) -> int | None:
        if lst is self.files:
            rows = self._visible_file_rows()
            return rows[-1] if rows else None
        for i in range(lst.count() - 1, -1, -1):
            it = lst.item(i)
            if it is not None and not it.isHidden():
                return i
        return None

    def _next_visible_row(
        self, lst: QtWidgets.QListWidget, start: int, delta: int
    ) -> int | None:
        if delta == 0:
            return start
        if lst is self.files:
            rows = self._visible_file_rows()
            if start not in rows:
                return rows[0] if delta > 0 and rows else rows[-1] if rows else None
            next_index = rows.index(start) + (1 if delta > 0 else -1)
            return rows[next_index] if 0 <= next_index < len(rows) else start
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
        if self.mainViews.currentWidget() is self.duplicateReviewView:
            if self._active_duplicate_scan_id is not None:
                self.cancel_duplicate_scan()
            elif self._duplicate_edit_mode:
                self.toggle_duplicate_edit_mode()
            else:
                self.show_tagging_workspace()
            return
        self._hide_tag_matches()
        fw = self.focusWidget()
        if isinstance(fw, QtWidgets.QLineEdit):
            fw.clearFocus()
            self.setFocus()
            return
        if self.photo_workspace.has_database_search:
            self.clear_db_search()

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
        raw = self.cmdLine.text() or ""
        self._close_command_line()
        raw = raw.removeprefix(":")
        raw = raw.lstrip()
        if not raw:
            return
        name_end = next(
            (index for index, character in enumerate(raw) if character.isspace()),
            len(raw),
        )
        name = raw[:name_end].casefold()
        args = [raw[name_end:]] if name_end < len(raw) else []
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
        self._tagHint.complete()
        raw = self.addEdit.text().strip()
        if raw and not self._tag_candidates(raw):
            self.statusBar().showMessage("No tag match")

    def _command_candidates(self, prefix: str) -> list[str]:
        out = [name for name in self._commands_by_name if name.startswith(prefix)]
        out.sort()
        return out

    def _tag_candidates(self, prefix: str) -> list[str]:
        prefix_cf = prefix.casefold()
        return [
            tag
            for tag in self._known_tag_candidates()
            if tag.casefold().startswith(prefix_cf)
        ]

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
        self._tagHint.reposition()

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:
        super().resizeEvent(event)
        self._position_cmd_hint()
        self._position_tag_hint()
        self._update_preview_pixmap()

    def _cmd_list_commands(self, _args: list[str] | None = None) -> None:
        lines: list[str] = []
        for spec in sorted(
            self._listed_actions,
            key=lambda action: action.command.name if action.command else action.id,
        ):
            command = spec.command
            if command is None:
                continue
            alias = (
                f" (aliases: {', '.join(command.aliases)})" if command.aliases else ""
            )
            labels = self._action_help_labels(spec)
            shorts = f" [{', '.join(labels)}]" if labels else ""
            lines.append(f"{command.name}{alias} — {spec.description}{shorts}")
        text = "\n".join(lines) if lines else "(no commands)"
        QtWidgets.QMessageBox.information(self, "Commands", text)

    def _cmd_quit(self, _args: list[str] | None = None) -> None:
        self.close()

    def _focus_first_visible_file(self) -> None:
        self._go_list_edge(self.files, to_end=False)
        self.files.setFocus()

    def _focus_pane_files(self) -> None:
        self._focus_pane(self.files)

    def _focus_pane_keywords(self) -> None:
        self._focus_pane(self.keywordsList)

    def _focus_pane_left(self) -> None:
        self._focus_pane_by_direction("left")

    def _focus_pane_right(self) -> None:
        self._focus_pane_by_direction("right")

    def _action_list_down(self) -> None:
        lst = self._resolve_current_list_widget()
        if lst is not None:
            self._move_list_selection(lst, +1)

    def _action_list_up(self) -> None:
        lst = self._resolve_current_list_widget()
        if lst is not None:
            self._move_list_selection(lst, -1)

    def _action_list_down_extend(self) -> None:
        if self.files.hasFocus():
            self._move_list_selection(self.files, +1, extend=True)

    def _action_list_up_extend(self) -> None:
        if self.files.hasFocus():
            self._move_list_selection(self.files, -1, extend=True)

    def _action_list_top(self) -> None:
        lst = self._resolve_current_list_widget()
        if lst is not None:
            self._go_list_edge(lst, to_end=False)

    def _action_list_bottom(self) -> None:
        lst = self._resolve_current_list_widget()
        if lst is not None:
            self._go_list_edge(lst, to_end=True)

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
            self._select_list_range(
                self.keywordsList, self._vim_visual_anchor, self._vim_visual_anchor
            )
        else:
            self.keywordsList.setSelectionMode(
                QtWidgets.QAbstractItemView.SelectionMode.SingleSelection
            )
            self._set_single_list_selection(self.keywordsList, self._vim_visual_anchor)

    def _select_list_range(
        self, lst: QtWidgets.QListWidget, start: int, end: int
    ) -> None:
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
        tags = [
            it.text().strip() for it in items if it is not None and it.text().strip()
        ]
        tags = dedupe_casefold(tags)
        if not tags:
            self.statusBar().showMessage("No tags selected")
            return
        self._yanked_tags = tags
        self.statusBar().showMessage(f"Yanked {len(tags)} tag(s)")

    def _open_selection_choice(self, title: str) -> str:
        dialog = QtWidgets.QMessageBox(self)
        dialog.setWindowTitle(title)
        dialog.setText("Open all selected photos or only the active photo?")
        all_button = dialog.addButton(
            "(A)ll", QtWidgets.QMessageBox.ButtonRole.AcceptRole
        )
        active_button = dialog.addButton(
            "(O)nly", QtWidgets.QMessageBox.ButtonRole.ActionRole
        )
        cancel_button = dialog.addButton(
            "(C)ancel", QtWidgets.QMessageBox.ButtonRole.RejectRole
        )
        dialog.setDefaultButton(cancel_button)
        choice_shortcuts = [
            QtGui.QShortcut(QtGui.QKeySequence("A"), dialog),
            QtGui.QShortcut(QtGui.QKeySequence("O"), dialog),
            QtGui.QShortcut(QtGui.QKeySequence("C"), dialog),
        ]
        choice_shortcuts[0].activated.connect(all_button.click)
        choice_shortcuts[1].activated.connect(active_button.click)
        choice_shortcuts[2].activated.connect(cancel_button.click)
        dialog.exec()
        if dialog.clickedButton() is all_button:
            return "all"
        if dialog.clickedButton() is active_button:
            return "active"
        return "cancel"

    def _paths_to_open(self, title: str) -> tuple[str, ...]:
        active_path = self.active_file_path()
        if active_path is None:
            self.statusBar().showMessage("No active photo")
            return ()
        selected_paths = tuple(self.selected_file_paths())
        if len(selected_paths) < 2:
            return (active_path,)
        choice = self._open_selection_choice(title)
        if choice == "all":
            return selected_paths
        if choice == "active":
            return (active_path,)
        return ()

    def _open_selected_photos(self) -> None:
        paths = self._paths_to_open("Open photos")
        if not paths:
            return
        try:
            self._file_actions.open_default(paths)
        except Exception as error:  # noqa: BLE001 - file-action boundary reports failures
            self._report_file_action_error("Open photos", error)

    def _open_selected_photos_in_gimp(self) -> None:
        paths = self._paths_to_open("Open photos in GIMP")
        if not paths:
            return
        try:
            self._file_actions.open_gimp(paths)
        except Exception as error:  # noqa: BLE001 - file-action boundary reports failures
            self._report_file_action_error("Open photos in GIMP", error)

    def _copy_selected_photo_paths(self) -> None:
        paths = tuple(self.selected_file_paths())
        if not paths:
            self.statusBar().showMessage("No active photo")
            return
        try:
            self._file_actions.copy_paths(paths)
        except Exception as error:  # noqa: BLE001 - file-action boundary reports failures
            self._report_file_action_error("Copy photo paths", error)
            return
        if len(paths) == 1:
            self.statusBar().showMessage(f'"{paths[0]}" was copied')
            return
        self.statusBar().showMessage(f"{len(paths)} file paths were copied")

    def _reveal_active_photo(self) -> None:
        path = self.active_file_path()
        if path is None:
            self.statusBar().showMessage("No active photo")
            return
        try:
            self._file_actions.reveal(path)
        except Exception as error:  # noqa: BLE001 - file-action boundary reports failures
            self._report_file_action_error("Reveal photo", error)
            return
        self.statusBar().showMessage(f'Revealing "{path}" in Explorer…')

    def _report_file_action_error(self, source: str, error: Exception) -> None:
        detail = str(error)
        self._record_session_error(source, detail)
        self.statusBar().showMessage(detail)

    def _show_file_context_menu(
        self,
        pos: QtCore.QPoint,
        modifiers: QtCore.Qt.KeyboardModifier | None = None,
    ) -> None:
        item = self.files.itemAt(pos)
        if item is None:
            return
        modifiers = modifiers or QtWidgets.QApplication.keyboardModifiers()
        control_pressed = bool(modifiers & QtCore.Qt.KeyboardModifier.ControlModifier)
        if control_pressed and not item.isSelected():
            self.files.setCurrentItem(
                item, QtCore.QItemSelectionModel.SelectionFlag.Select
            )
        elif not item.isSelected():
            self.files.setCurrentItem(
                item, QtCore.QItemSelectionModel.SelectionFlag.ClearAndSelect
            )
        else:
            self.files.setCurrentItem(
                item, QtCore.QItemSelectionModel.SelectionFlag.NoUpdate
            )
        self.on_selection_changed()

        menu = QtWidgets.QMenu(self.files)
        menu.addAction("Open", self._open_selected_photos)
        menu.addAction("Open in GIMP", self._open_selected_photos_in_gimp)
        menu.addAction("Copy file path", self._copy_selected_photo_paths)
        menu.addAction("Reveal in Explorer", self._reveal_active_photo)
        directory_name = Path(item.text()).parent.name
        if directory_name:
            menu.addAction(
                f'Exclude folders named "{directory_name}"',
                lambda: self._exclude_containing_folder(directory_name),
            )
        menu.popup(self.files.viewport().mapToGlobal(pos))

    def _exclude_containing_folder(self, directory_name: str) -> None:
        """Add the clicked photo's containing folder name as an exclusion."""
        self.directoryExcludeEdit.setText(directory_name)
        self.apply_directory_exclusion()

    def _yank_current_file_tags(self) -> None:
        files = self.selected_file_paths()
        if not files:
            self.statusBar().showMessage("No file selected")
            return
        state = self._keywords_cache.get(files[0])
        if state is None:
            self.statusBar().showMessage("Tags are still loading")
            return
        self._yanked_tags = state.iptc
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
        if self._reject_invalid_iptc_keywords(self._yanked_tags):
            return
        target = files[0]
        pending_mutation = self._begin_pending_tag_mutation(
            [target], [TagIntent.add(tag) for tag in self._yanked_tags]
        )
        self.statusBar().showMessage(f"Queued paste ({len(self._yanked_tags)} tag(s))")
        self._enqueue_tag_mutation(
            [target],
            lambda paths: self.tag_mutations.add_tags(
                paths,
                self._yanked_tags,
                keep_backup=self.keepBackup.isChecked(),
                load_state=self.exif.read_keywords,
            ),
            pending_mutation,
            f"Pasted {len(self._yanked_tags)} tag(s)",
        )

    def _focus_pane(self, pane: QtWidgets.QListWidget) -> None:
        if pane.count() > 0 and pane.currentRow() < 0:
            if pane is self.keywordsList and not self._vim_visual_keywords:
                self._set_single_list_selection(pane, 0)
            else:
                pane.setCurrentRow(0)
        elif (
            pane is self.keywordsList
            and not self._vim_visual_keywords
            and pane.currentRow() >= 0
        ):
            self._set_single_list_selection(pane, pane.currentRow())
        pane.setFocus()

    def _focus_next_pane(self) -> None:
        panes = [self.files, self.keywordsList]
        focus = self.focusWidget()
        current = next((pane for pane in panes if focus is pane), None)
        if current is None:
            self._focus_pane(self.files)
            return
        self._focus_pane(panes[(panes.index(current) + 1) % len(panes)])

    def _focus_pane_by_direction(self, direction: str) -> None:
        focus = self.focusWidget()
        if direction == "left" and focus is self.keywordsList:
            self._focus_pane(self.files)
        elif direction == "right" and focus is self.files:
            self._focus_pane(self.keywordsList)

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
            self.handle_dropped_urls(event.mimeData().urls())
            event.acceptProposedAction()
            return
        super().dropEvent(event)

    def add_files(self, paths: list[str]) -> None:
        before = self.photo_workspace.snapshot()
        snapshot = self.photo_workspace.add_paths(
            normalize_path(path) for path in paths
        )
        added_paths = [path for path in snapshot.paths if path not in before.paths]
        if added_paths:
            self._hide_files_pane_message()
        self._render_photo_workspace_snapshot(snapshot, list(before.selected_paths))
        self.statusBar().showMessage(f"Added {len(added_paths)} files")
        if self.onlyUntagged.isChecked():
            self.apply_iptc_filter_async()
        if added_paths:
            self._set_last_folder(str(Path(added_paths[-1]).parent))
        root = self._index_root_for_paths(self.all_file_paths())
        if root:
            self._index_root = root
            self._schedule_index_sync(root, self.all_file_paths())
            if added_paths:
                self._index_missing_paths(root, added_paths)

    def replace_photo_workspace(
        self,
        paths: list[str],
        *,
        invalidate_discoveries: bool = True,
        paths_are_normalized: bool = False,
        render_in_batches: bool = False,
        on_rendered: Callable[[], None] | None = None,
    ) -> None:
        # BackgroundCoordinator canonicalizes discovery paths before delivering
        # them. Re-resolving thousands of them here can block the UI, especially
        # on Windows shares.
        normalized_paths = (
            list(paths)
            if paths_are_normalized
            else [normalize_path(path) for path in paths]
        )
        self._active_search_request = None
        self._displayed_search_request = None
        self._displayed_search_generation = None
        self._displayed_search_query = None
        self._active_known_tags_request = None
        self._active_index_refresh_request = None
        self._clear_iptc_empty_refresh_state()
        self._background_coordinator.invalidate_search()
        self._background_coordinator.invalidate_iptc_empty()
        self._background_coordinator.invalidate_known_tags()
        if invalidate_discoveries:
            self._active_replacement_discovery = None
            self._pending_additive_discoveries.clear()
        self._tag_mutation_coordinator.replace_workspace(normalized_paths)
        self._batch_summary_generation += 1
        # Cancel in-flight async work that would render stale UI.
        self._selection_token += 1
        self._preview_token += 1
        # Reset caches tied to previous file lists.
        self._keywords_cache = {}
        self._index_root = None
        self._search_restore_scroll = None
        self._filename_filter_restore_scroll = None
        self._directory_exclusion_restore_scroll = None
        self._filename_filter_timer.stop()
        self.filenameFilterEdit.blockSignals(True)
        self.filenameCaseSensitiveBtn.blockSignals(True)
        try:
            self.filenameFilterEdit.clear()
            self.filenameCaseSensitiveBtn.setChecked(False)
            self.directoryExcludeEdit.clear()
            self._clear_directory_exclusion_error()
        finally:
            self.filenameFilterEdit.blockSignals(False)
            self.filenameCaseSensitiveBtn.blockSignals(False)

        snapshot = self.photo_workspace.reload_paths(normalized_paths)
        self._files_render_token += 1
        self.files.setEnabled(True)
        self._hide_files_render_progress()
        if render_in_batches:
            self._render_photo_workspace_in_batches(
                snapshot, self._files_render_token, on_rendered
            )
            return
        self._render_photo_workspace(snapshot)
        self.on_selection_changed()
        if on_rendered is not None:
            on_rendered()

    def _reset_files_pane_for_reload(self) -> None:
        self.replace_photo_workspace([])

    def add_folder_dialog(self) -> None:
        default_dir = self._get_default_folder_for_dialog()
        if default_dir:
            folder = QtWidgets.QFileDialog.getExistingDirectory(
                self, "Choose folder", default_dir
            )
        else:
            folder = QtWidgets.QFileDialog.getExistingDirectory(self, "Choose folder")
        if folder:
            if self.mainViews.currentWidget() is self.duplicateReviewView:
                self._duplicate_folder_scope_after_load = normalize_path(folder)
                self._invalidate_duplicate_scope_for_folder_load()
            self._start_folder_discovery(folder)

    def _start_folder_discovery(self, folder: str) -> None:
        # A folder selection replaces the current workspace before discovery starts.
        had_prepared_index_scope = (
            self._prepared_duplicate_scope is not None
            and self._prepared_duplicate_scope.kind is DuplicateScopeKind.INDEX_DATABASE
        )
        self._reset_files_pane_for_reload()
        if self._duplicate_folder_scope_after_load is not None:
            self.duplicateScopePathLabel.setText(
                self._duplicate_folder_scope_after_load
            )
        elif had_prepared_index_scope:
            self._duplicate_scope_choice_changed()
        else:
            self._refresh_duplicate_scope_controls()
        self._hide_files_pane_message()
        self._show_files_render_progress()
        self.statusBar().showMessage("Loading...")
        request = self._background_coordinator.replace_workspace_from_folder(folder)
        self._active_replacement_discovery = request
        self._pending_additive_discoveries.clear()
        self._coordinator_workspace_generation = request.workspace_generation
        self._set_last_folder(folder)

    def add_dropped_directory(self, folder: str) -> None:
        """Discover one dropped directory without blocking the current workspace."""
        request = self._background_coordinator.add_dropped_directory(folder)
        if self._coordinator_workspace_generation is None:
            self._coordinator_workspace_generation = request.workspace_generation
        self._pending_additive_discoveries.add(request.request_id)
        self.statusBar().showMessage("Loading photos…")

    def handle_dropped_urls(self, urls: list[QtCore.QUrl]) -> None:
        files: list[str] = []
        directories: list[str] = []
        for url in urls:
            if not url.isLocalFile():
                continue
            path = Path(url.toLocalFile())
            if path.is_dir():
                directories.append(str(path))
            elif path.suffix.lower() in SUPPORTED_PHOTO_EXTENSIONS:
                files.append(str(path))
        if files:
            self.add_files(files)
        for directory in directories:
            self.add_dropped_directory(directory)

    def _handle_coordinator_event(self, event: CoordinatorEvent) -> None:
        if isinstance(
            event,
            (
                IndexEnsureCompleted,
                IndexWriteCompleted,
                IndexWriteFailed,
                IndexRefreshCompleted,
                IndexRefreshProgress,
                IndexRefreshFailed,
                IndexStaleResultEvicted,
                IndexSearchCompleted,
                IptcEmptyIndexCompleted,
                KnownTagsCompleted,
                IndexReadFailed,
            ),
        ):
            self._handle_index_event(event)
            return
        self._handle_discovery_event(event)

    def _handle_index_event(
        self,
        event: (
            IndexEnsureCompleted
            | IndexWriteCompleted
            | IndexWriteFailed
            | IndexRefreshCompleted
            | IndexRefreshProgress
            | IndexRefreshFailed
            | IndexStaleResultEvicted
            | IndexSearchCompleted
            | IptcEmptyIndexCompleted
            | KnownTagsCompleted
            | IndexReadFailed
        ),
    ) -> None:
        if isinstance(
            event,
            (
                IndexSearchCompleted,
                IptcEmptyIndexCompleted,
                KnownTagsCompleted,
                IndexReadFailed,
            ),
        ):
            self._handle_index_read_event(event)
            return
        if isinstance(event, IndexStaleResultEvicted):
            self._handle_stale_result_evicted(event)
            return
        if isinstance(
            event, (IndexRefreshCompleted, IndexRefreshProgress, IndexRefreshFailed)
        ):
            self._handle_index_refresh_event(event)
            return
        if isinstance(event, IndexEnsureCompleted):
            self._index_sync_inflight.discard(event.root)
            if event.root != self._index_root:
                return
            if self.mainViews.currentWidget() is self.duplicateReviewView:
                self._ensure_duplicate_scope_prepared()
            if isinstance(event.result, IndexSyncResult):
                if not self._has_active_search_for(event.root):
                    self.statusBar().showMessage(
                        f"Index ready: {event.result.updated_count} updated, "
                        f"{event.result.deleted_count} removed"
                    )
                self.force_refresh_known_tags()
                if self._iptc_empty_waiting_for_index:
                    self._start_deferred_iptc_empty_filter(event.root)
                else:
                    self._check_iptc_empty_results_after_index_update(event.root)
            elif event.result is None:
                self._active_index_refresh_request = self._background_coordinator.refresh_if_stale(
                    event.root,
                    workspace_generation=self._tag_mutation_coordinator.workspace_generation,
                )
                if not self._has_active_search_for(event.root):
                    self.statusBar().showMessage("Index ready")
            elif getattr(event.result, "complete", True) is False:
                if not self._has_active_search_for(event.root):
                    self.statusBar().showMessage("Rebuilding canonical IPTC index…")
            return
        if isinstance(event, IndexWriteFailed):
            self._index_sync_inflight.discard(event.root)
        if event.root != self._index_root:
            return
        if isinstance(event, IndexWriteFailed):
            self._record_session_error("Index update", event.error)
            if not self._has_active_search_for(event.root):
                self.statusBar().showMessage("Index update failed")
            return
        self.force_refresh_known_tags()

    def _has_active_search_for(self, root: str) -> bool:
        request = self._active_search_request
        return request is not None and request.root == root

    def _clear_iptc_empty_refresh_state(self) -> None:
        self._iptc_empty_filter_request = None
        self._iptc_empty_refresh_check_request = None
        self._iptc_empty_refresh_apply_request = None
        self._iptc_empty_filter_operation_id = None
        self._iptc_empty_root = None
        self._iptc_empty_waiting_for_index = False
        self._iptc_empty_unknown_paths.clear()
        self._iptc_empty_refresh_available = False
        if hasattr(self, "iptcEmptyRefreshOffer"):
            self.iptcEmptyRefreshOffer.hide()

    def _start_deferred_iptc_empty_filter(self, root: str) -> None:
        """Start a filter read after its startup index work has completed."""
        if not self._iptc_empty_waiting_for_index or self._iptc_empty_root != root:
            return
        snapshot = self.photo_workspace.snapshot()
        operation_id = self._iptc_empty_filter_operation_id
        if operation_id is None or snapshot.filter_operation_id != operation_id:
            return
        self._iptc_empty_waiting_for_index = False
        self._iptc_empty_filter_request = self._background_coordinator.load_iptc_empty(
            root,
            snapshot.paths,
            workspace_generation=self._tag_mutation_coordinator.workspace_generation,
        )

    def _has_current_iptc_empty_view(self, root: str) -> bool:
        snapshot = self.photo_workspace.snapshot()
        return (
            self._iptc_empty_root == root
            and self.photo_workspace.iptc_empty_membership is not None
            and root == self._index_root
            and snapshot.view_mode is PhotoWorkspaceViewMode.IPTC_EMPTY
            and snapshot.filter_operation_id is None
        )

    def _check_iptc_empty_results_after_index_update(self, root: str) -> None:
        """Compare a completed normal index update without changing the view."""
        if not self._has_current_iptc_empty_view(root):
            return
        self._iptc_empty_refresh_available = False
        self.iptcEmptyRefreshOffer.hide()
        self._iptc_empty_refresh_check_request = self._background_coordinator.load_iptc_empty(
            root,
            self.photo_workspace.snapshot().paths,
            workspace_generation=self._tag_mutation_coordinator.workspace_generation,
        )

    def _handle_iptc_empty_index_event(
        self, event: IptcEmptyIndexCompleted | IndexReadFailed
    ) -> None:
        request = event.request
        if (
            request.workspace_generation
            != self._tag_mutation_coordinator.workspace_generation
        ):
            return
        if request == self._iptc_empty_filter_request:
            self._iptc_empty_filter_request = None
            if isinstance(event, IndexReadFailed):
                before = self.selected_file_paths()
                snapshot = self.photo_workspace.clear_iptc_empty_filter()
                self._clear_iptc_empty_refresh_state()
                self._render_photo_workspace_snapshot(
                    snapshot, before, scroll_active_to_top=True
                )
                self._record_session_error("IPTC-empty index query", event.error)
                self.statusBar().showMessage("Filtering IPTC-empty failed")
                return
            if not isinstance(event.result, IptcEmptyIndexResult):
                return
            operation_id = self._iptc_empty_filter_operation_id
            if operation_id is None or request.root != self._iptc_empty_root:
                return
            before = self.selected_file_paths()
            snapshot = self.photo_workspace.accept_indexed_iptc_empty_filter(
                operation_id, event.result.paths
            )
            if snapshot.view_mode is not PhotoWorkspaceViewMode.IPTC_EMPTY:
                return
            membership = self.photo_workspace.iptc_empty_membership
            if membership is None:
                return
            self._iptc_empty_unknown_paths = set(event.result.unknown_paths) & set(
                membership
            )
            self._render_photo_workspace_snapshot(snapshot, before)
            self.statusBar().showMessage("IPTC-empty results ready")
            return

        if request == self._iptc_empty_refresh_check_request:
            self._iptc_empty_refresh_check_request = None
            snapshot = self.photo_workspace.snapshot()
            if (
                isinstance(event, IndexReadFailed)
                or not isinstance(event.result, IptcEmptyIndexResult)
                or not self._has_current_iptc_empty_view(request.root)
            ):
                return
            if (
                frozenset(event.result.paths) & frozenset(snapshot.paths)
                != self.photo_workspace.iptc_empty_membership
            ):
                self._iptc_empty_refresh_available = True
                self.iptcEmptyRefreshOffer.show()
            return

        if request != self._iptc_empty_refresh_apply_request:
            return
        self._iptc_empty_refresh_apply_request = None
        if (
            isinstance(event, IndexReadFailed)
            or not isinstance(event.result, IptcEmptyIndexResult)
            or not self._has_current_iptc_empty_view(request.root)
        ):
            return
        before = self.selected_file_paths()
        snapshot = self.photo_workspace.refresh_indexed_iptc_empty_filter(
            event.result.paths
        )
        membership = self.photo_workspace.iptc_empty_membership
        if membership is None:
            return
        self._iptc_empty_unknown_paths = set(event.result.unknown_paths) & set(
            membership
        )
        self._render_photo_workspace_snapshot(snapshot, before)
        self.statusBar().showMessage("IPTC-empty results refreshed")

    def _handle_index_refresh_event(
        self, event: IndexRefreshCompleted | IndexRefreshProgress | IndexRefreshFailed
    ) -> None:
        request = event.request
        if request.kind is IndexRefreshKind.STALE_RESULT_REPAIR:
            self._handle_stale_result_repair_event(event)
            return
        if (
            request != self._active_index_refresh_request
            or request.workspace_generation
            != self._tag_mutation_coordinator.workspace_generation
            or request.root != self._index_root
        ):
            return
        if isinstance(event, IndexRefreshProgress):
            self._show_refresh_progress(event.result)
            return
        self._active_index_refresh_request = None
        self._stop_refresh_discovery_animation()
        if isinstance(event, IndexRefreshFailed):
            self._iptc_empty_refresh_available = False
            self._iptc_empty_refresh_check_request = None
            self.iptcEmptyRefreshOffer.hide()
            self._record_session_error("Index refresh", event.error)
            self.indexRepairStatusLabel.setText("Index refresh failed")
            if not self._has_active_search_for(request.root):
                label = (
                    "Reindex failed"
                    if request.kind is IndexRefreshKind.MANUAL
                    else "Index refresh failed"
                )
                self.statusBar().showMessage(label)
            return
        if self._iptc_empty_waiting_for_index:
            self._start_deferred_iptc_empty_filter(request.root)
        # A fresh automatic check has no refresh result and must not replace
        # ordinary feedback or look like a completed user-visible operation.
        if event.result is None:
            return
        self.indexRepairStatusLabel.setText("Index refresh complete")
        self.force_refresh_known_tags()
        self._check_iptc_empty_results_after_index_update(request.root)
        if self._has_active_search_for(request.root):
            return
        if isinstance(event.result, IndexSyncResult):
            prefix = (
                "Reindex complete"
                if request.kind is IndexRefreshKind.MANUAL
                else "Index refreshed"
            )
            self.statusBar().showMessage(
                f"{prefix}: {event.result.updated_count} updated, "
                f"{event.result.deleted_count} removed"
            )
            self.indexRepairStatusLabel.setText(
                f"Index refresh complete: {event.result.updated_count} updated, "
                f"{event.result.deleted_count} removed"
            )
            return
        self.statusBar().showMessage(
            "Reindex complete"
            if request.kind is IndexRefreshKind.MANUAL
            else "Index refreshed"
        )

    def _show_refresh_progress(self, progress: object) -> None:
        if not isinstance(progress, IndexRefreshStep):
            return
        now = time.monotonic()
        if now - self._last_refresh_status_at < 1.0:
            return
        self._last_refresh_status_at = now
        if progress.phase == "discovering":
            if self._refresh_discovery_progress is None:
                self._refresh_discovery_hidden_letter_index = len("Discovering")
                self._refresh_discovery_timer.start()
            self._refresh_discovery_progress = progress
            self._update_refresh_discovery_status()
            return
        self._stop_refresh_discovery_animation()
        self.indexRepairStatusLabel.setText("Reconciling index…")

    def _advance_refresh_discovery_animation(self) -> None:
        if self._refresh_discovery_progress is not None:
            self._update_refresh_discovery_status()

    def _update_refresh_discovery_status(self) -> None:
        progress = self._refresh_discovery_progress
        if progress is None:
            return
        discovering, self._refresh_discovery_hidden_letter_index = self._loading_text(
            "Discovering", self._refresh_discovery_hidden_letter_index
        )
        prefix = "Resumed; " if progress.resumed else ""
        self.indexRepairStatusLabel.setText(
            f"{prefix}{discovering} images for DB index… "
            f"{progress.indexed_count} indexed"
        )

    def _stop_refresh_discovery_animation(self) -> None:
        self._refresh_discovery_timer.stop()
        self._refresh_discovery_progress = None
        self._refresh_discovery_hidden_letter_index = 0

    def _handle_stale_result_repair_event(
        self, event: IndexRefreshCompleted | IndexRefreshFailed
    ) -> None:
        request = event.request
        if self._stale_result_repairs.get(request.root) != request:
            return
        del self._stale_result_repairs[request.root]
        if isinstance(event, IndexRefreshFailed):
            self._record_session_error("Index repair", event.error)
            self.indexRepairStatusLabel.setText(f"Index repair failed: {event.error}")
            return

        if not self._is_current_stale_result_repair(request):
            self.indexRepairStatusLabel.setText("Index repair complete")
            return

        self._rerun_stale_result_repair_query(request)
        self.indexRepairStatusLabel.setText(
            "Local index repair complete; refreshing search…"
        )

    def _handle_stale_result_evicted(self, event: IndexStaleResultEvicted) -> None:
        request = event.request
        if self._stale_result_repairs.get(request.root) != request:
            return
        if self._is_current_stale_result_repair(request):
            self._rerun_stale_result_repair_query(request)
        self.indexRepairStatusLabel.setText(
            "Missing result removed; checking parent folder…"
        )

    def _rerun_stale_result_repair_query(self, request: IndexRefreshRequest) -> None:
        self._active_known_tags_request = self._background_coordinator.load_known_tags(
            request.root,
            workspace_generation=self._tag_mutation_coordinator.workspace_generation,
        )
        self._active_search_request = self._background_coordinator.search_index(
            request.root,
            request.query or "",
            workspace_generation=self._tag_mutation_coordinator.workspace_generation,
        )
        self._update_view_indicator(self.photo_workspace.snapshot())

    def _is_current_stale_result_repair(self, request: IndexRefreshRequest) -> bool:
        displayed = self._displayed_search_request
        return (
            request.query is not None
            and (
                self._active_search_request is None
                or (
                    self._active_search_request.root == request.root
                    and self._active_search_request.query == request.query
                )
            )
            and displayed is not None
            and self.photo_workspace.has_database_search
            and request.root == self._index_root
            and (displayed.root, displayed.query) == (request.root, request.query)
        )

    def _handle_index_read_event(
        self,
        event: IptcEmptyIndexCompleted
        | IndexSearchCompleted
        | KnownTagsCompleted
        | IndexReadFailed,
    ) -> None:
        request = event.request
        if request.kind is IndexReadKind.IPTC_EMPTY:
            self._handle_iptc_empty_index_event(event)
            return
        if request.kind is IndexReadKind.SEARCH:
            if (
                request != self._active_search_request
                or request.workspace_generation
                != self._tag_mutation_coordinator.workspace_generation
                or request.root != self._index_root
            ):
                return
            self._active_search_request = None
            if isinstance(event, IndexReadFailed):
                self._record_session_error("Index search", event.error)
                self._update_view_indicator(self.photo_workspace.snapshot())
                self.statusBar().showMessage("Search failed")
                return
            self._displayed_search_request = request
            self._displayed_search_query = request.query
            self._apply_db_search_result(event.paths)
            self._displayed_search_generation = (
                self._tag_mutation_coordinator.workspace_generation
            )
            return

        if (
            request != self._active_known_tags_request
            or request.workspace_generation
            != self._tag_mutation_coordinator.workspace_generation
            or request.root != self._index_root
        ):
            return
        if isinstance(event, IndexReadFailed):
            self._record_session_error("Tag autocomplete refresh", event.error)
            self.statusBar().showMessage("Tag autocomplete refresh failed")
            return
        if isinstance(event, KnownTagsCompleted):
            self._known_tags_snapshot = set(event.tags)
            self._known_tags_root = request.root

    def _handle_discovery_event(self, event: DiscoveryEvent) -> None:
        if event.kind is DiscoveryKind.REPLACEMENT:
            request = self._active_replacement_discovery
            if (
                request is None
                or event.workspace_generation != request.workspace_generation
                or event.request_id != request.request_id
            ):
                return
            self._active_replacement_discovery = None
            if isinstance(event, DiscoveryCompleted):

                def finish_render() -> None:
                    if (
                        self.files.count() > 0
                        and self.mainViews.currentWidget() is self.taggingWorkspaceView
                    ):
                        self.files.setFocus()

                self.replace_photo_workspace(
                    list(event.paths),
                    invalidate_discoveries=False,
                    paths_are_normalized=True,
                    render_in_batches=True,
                    on_rendered=finish_render,
                )
                # All discovered paths are beneath event.root. Resolving the
                # root from every path would synchronously stat every photo on
                # the UI thread before the first render batch can run.
                root = self._index_root_for_paths([event.root])
                if root:
                    self._index_root = root
                selected_duplicate_folder = self._duplicate_folder_scope_after_load
                self._duplicate_folder_scope_after_load = None
                if selected_duplicate_folder == normalize_path(event.root):
                    self._prepare_discovered_duplicate_subfolder(
                        event.root, event.paths
                    )
                else:
                    self._refresh_duplicate_scope_controls()
                self._schedule_index_sync(
                    root, list(event.paths), paths_are_normalized=True
                )
                if (
                    selected_duplicate_folder is None
                    and self.mainViews.currentWidget() is self.duplicateReviewView
                ):
                    self._ensure_duplicate_scope_prepared()
            else:
                self._duplicate_folder_scope_after_load = None
                self._refresh_duplicate_scope_controls()
                self._record_session_error("Photo discovery", event.error)
                self._hide_files_render_progress()
                self._show_files_pane_message("No photos loaded")
                self.statusBar().showMessage(f"Loading photos failed: {event.error}")
            return

        if (
            event.workspace_generation != self._coordinator_workspace_generation
            or event.request_id not in self._pending_additive_discoveries
        ):
            return
        self._pending_additive_discoveries.remove(event.request_id)
        if isinstance(event, DiscoveryCompleted):
            self.add_files(list(event.paths))
            if self._pending_additive_discoveries:
                self.statusBar().showMessage("Loading photos…")
        else:
            self._record_session_error("Photo discovery", event.error)
            self.statusBar().showMessage(f"Loading photos failed: {event.error}")

    def _show_files_pane_message(self, message: str) -> None:
        if message == self._loading_photos_message:
            self._loading_photos_hidden_letter_index = 0
            self.filesPaneMessage.setText(message)
            self._loading_photos_timer.start()
        else:
            self._loading_photos_timer.stop()
            self.filesPaneMessage.setText(message)
        self._position_files_pane_message()
        self.filesPaneMessage.show()

    def _advance_loading_photos_animation(self) -> None:
        if self.filesPaneMessage.isVisible():
            text, self._loading_photos_hidden_letter_index = self._loading_text(
                self._loading_photos_message,
                self._loading_photos_hidden_letter_index,
            )
            self.filesPaneMessage.setText(text)
        if self.filesRenderProgress.isVisible():
            self._update_files_render_progress_text()

    @staticmethod
    def _loading_text(message: str, hidden_letter: int) -> tuple[str, int]:
        """Hide one alphabetic character and restore the full text between cycles."""
        letter_count = sum(character.isalpha() for character in message)
        if hidden_letter >= letter_count:
            return message, 0
        rendered: list[str] = []
        letter_index = 0
        for character in message:
            if character.isalpha():
                rendered.append(" " if letter_index == hidden_letter else character)
                letter_index += 1
            else:
                rendered.append(character)
        return "".join(rendered), hidden_letter + 1

    def _hide_files_pane_message(self) -> None:
        self.filesPaneMessage.hide()
        if not self.filesRenderProgress.isVisible():
            self._loading_photos_timer.stop()

    def _show_files_render_progress(
        self, loaded: int | None = None, total: int | None = None
    ) -> None:
        if not self.filesRenderProgress.isVisible():
            self._files_render_hidden_letter_index = len("Loading")
        self._files_render_loaded = loaded
        self._files_render_total = total
        self.filterInfoLabel.hide()
        self.filterSummary.show()
        self._update_files_render_progress_text()
        self.filesRenderProgress.show()
        if self.files.count() == 0:
            self.filesPaneLoadingIcon.show()
            self._position_files_pane_message()
        else:
            self.filesPaneLoadingIcon.hide()
        self._loading_photos_timer.start()

    def _update_files_render_progress_text(self) -> None:
        loading, self._files_render_hidden_letter_index = self._loading_text(
            "Loading", self._files_render_hidden_letter_index
        )
        self.filesRenderProgressLabel.setText(loading)
        if self._files_render_total is not None:
            self.filesRenderProgressCountLabel.setText(
                f"{self._format_loading_count(self._files_render_loaded)} / "
                f"{self._format_loading_count(self._files_render_total)}"
            )
        else:
            self.filesRenderProgressCountLabel.clear()

    @staticmethod
    def _format_loading_count(number: int | None) -> str:
        return f"{number or 0:,}".replace(",", " ")

    def _hide_files_render_progress(self) -> None:
        self.filesRenderProgress.hide()
        self.filesPaneLoadingIcon.hide()
        self._update_view_indicator(self.photo_workspace.snapshot())
        if not self.filesPaneMessage.isVisible():
            self._loading_photos_timer.stop()

    def _position_files_pane_message(self) -> None:
        viewport = self.files.viewport().rect()
        self.filesPaneMessage.setGeometry(viewport)
        self.filesPaneLoadingIcon.move(
            (viewport.width() - self.filesPaneLoadingIcon.width()) // 2,
            (viewport.height() - self.filesPaneLoadingIcon.height()) // 2,
        )

    def _set_last_folder(self, folder: str) -> None:
        try:
            p = Path(folder).resolve()
        except (OSError, RuntimeError):
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
            except (OSError, RuntimeError):
                last_folder = None

        sel = self.selected_file_paths()
        if sel:
            try:
                return str(Path(sel[0]).resolve().parent)
            except (OSError, RuntimeError):
                return str(Path(sel[0]).parent)

        if self.files.count() > 0:
            try:
                return str(Path(self.files.item(0).text()).resolve().parent)
            except (OSError, RuntimeError):
                return str(Path(self.files.item(0).text()).parent)
        return None

    def _render_photo_workspace(self, snapshot: PhotoWorkspaceSnapshot) -> None:
        # A synchronous transition supersedes any queued replacement batches.
        self._files_render_token += 1
        self._update_view_indicator(snapshot)
        self.onlyUntagged.blockSignals(True)
        self.files.blockSignals(True)
        try:
            self.onlyUntagged.setChecked(
                snapshot.view_mode is PhotoWorkspaceViewMode.IPTC_EMPTY
            )
            self._clear_pending_mutation_spinner_items()
            self._file_items_by_path.clear()
            self.files.clear()
            visible_paths = set(snapshot.visible_paths)
            selected_paths = set(snapshot.selected_paths)
            for path in snapshot.paths:
                item = QtWidgets.QListWidgetItem(path)
                self._set_file_mutation_indicator(item, path, path_is_normalized=True)
                self.files.addItem(item)
                self._file_items_by_path[path] = item
                item.setHidden(path not in visible_paths)
                item.setSelected(path in selected_paths)
            if snapshot.active_path is not None:
                item = self._find_item_by_path(snapshot.active_path)
                if item is not None:
                    self.files.setCurrentItem(item)
        finally:
            self.files.blockSignals(False)
            self.onlyUntagged.blockSignals(False)
        self._update_files_pane_empty_state(snapshot)

    def _render_photo_workspace_in_batches(
        self,
        snapshot: PhotoWorkspaceSnapshot,
        token: int,
        on_rendered: Callable[[], None] | None,
    ) -> None:
        """Populate a large replacement view without monopolizing the UI thread."""
        self._hide_files_pane_message()
        self._update_view_indicator(snapshot)
        self.onlyUntagged.blockSignals(True)
        try:
            self.onlyUntagged.setChecked(
                snapshot.view_mode is PhotoWorkspaceViewMode.IPTC_EMPTY
            )
        finally:
            self.onlyUntagged.blockSignals(False)
        self.files.blockSignals(True)
        try:
            self._clear_pending_mutation_spinner_items()
            self._file_items_by_path.clear()
            self.files.clear()
        finally:
            self.files.blockSignals(False)

        paths = snapshot.paths
        self.files.setEnabled(False)
        self._show_files_render_progress(0, len(paths))
        visible_paths = set(snapshot.visible_paths)
        selected_paths = set(snapshot.selected_paths)
        position = 0

        def render_next_batch() -> None:
            nonlocal position
            if token != self._files_render_token:
                return
            end = min(position + FILE_PANE_RENDER_BATCH_SIZE, len(paths))
            self.files.blockSignals(True)
            try:
                for path in paths[position:end]:
                    item = QtWidgets.QListWidgetItem(path)
                    self._set_file_mutation_indicator(
                        item, path, path_is_normalized=True
                    )
                    self.files.addItem(item)
                    self._file_items_by_path[path] = item
                    item.setHidden(path not in visible_paths)
                    item.setSelected(path in selected_paths)
            finally:
                self.files.blockSignals(False)
            position = end
            self._show_files_render_progress(position, len(paths))
            if position < len(paths):
                # Yield to the platform event queue so mouse and paint events
                # are not starved by a long sequence of zero-delay batches.
                QtCore.QTimer.singleShot(1, render_next_batch)
                return
            self.files.setEnabled(True)
            self._hide_files_render_progress()
            self._update_files_pane_empty_state(snapshot)
            if snapshot.active_path is not None:
                item = self._find_item_by_path(snapshot.active_path)
                if item is not None:
                    self.files.setCurrentItem(item)
            self.on_selection_changed()
            if on_rendered is not None:
                on_rendered()

        QtCore.QTimer.singleShot(0, render_next_batch)

    def _clear_pending_mutation_spinner_items(self) -> None:
        self._pending_mutation_spinner_items.clear()
        self._pending_mutation_spinner_timer.stop()

    def _sync_pending_mutation_spinner_timer(self) -> None:
        if self._pending_mutation_spinner_items:
            if not self._pending_mutation_spinner_timer.isActive():
                self._pending_mutation_spinner_timer.start()
        else:
            self._pending_mutation_spinner_timer.stop()

    def _advance_pending_mutation_spinners(self) -> None:
        self._pending_mutation_spinner_angle = (
            self._pending_mutation_spinner_angle + 6
        ) % 360
        icon = _loading_spinner_icon(16, self._pending_mutation_spinner_angle)
        for path, item in tuple(self._pending_mutation_spinner_items.items()):
            if item.listWidget() is self.files:
                item.setIcon(icon)
            else:
                self._pending_mutation_spinner_items.pop(path, None)
        self._sync_pending_mutation_spinner_timer()

    def _set_file_mutation_indicator(
        self,
        item: QtWidgets.QListWidgetItem,
        path: str,
        *,
        path_is_normalized: bool = False,
    ) -> None:
        normalized_path = path if path_is_normalized else normalize_path(path)
        status = self._tag_mutation_coordinator.status_for(normalized_path)
        if status is MutationStatus.PENDING:
            self._pending_mutation_spinner_items[normalized_path] = item
            item.setIcon(
                _loading_spinner_icon(16, self._pending_mutation_spinner_angle)
            )
            item.setToolTip("Saving tag changes")
        elif status is MutationStatus.FAILED:
            self._pending_mutation_spinner_items.pop(normalized_path, None)
            item.setIcon(
                self.style().standardIcon(
                    QtWidgets.QStyle.StandardPixmap.SP_MessageBoxInformation
                )
            )
            item.setToolTip("Tag changes need attention; retry with :retry")
        elif normalized_path in self._iptc_empty_unknown_paths:
            self._pending_mutation_spinner_items.pop(normalized_path, None)
            item.setIcon(_unverified_iptc_icon())
            item.setToolTip("IPTC keywords could not be verified")
        else:
            self._pending_mutation_spinner_items.pop(normalized_path, None)
            item.setIcon(QtGui.QIcon())
            item.setToolTip("")
        self._sync_pending_mutation_spinner_timer()

    def _refresh_file_mutation_indicators(self, paths: list[str]) -> None:
        for path in paths:
            item = self._find_item_by_path(path)
            if item is not None:
                self._set_file_mutation_indicator(item, path)

    def _refresh_mutation_status_view(self) -> None:
        active_path = self.active_file_path()
        status = (
            self._tag_mutation_coordinator.status_for(active_path)
            if active_path is not None
            else None
        )
        if status is MutationStatus.PENDING:
            self.mutationStatusLabel.setText("Saving tag changes…")
        elif status is MutationStatus.FAILED:
            self.mutationStatusLabel.setText("Tag changes need attention — use :retry")
        else:
            self.mutationStatusLabel.setText("")

    def all_file_paths(self) -> list[str]:
        return list(self.photo_workspace.snapshot().paths)

    def selected_file_paths(self) -> list[str]:
        return list(self.photo_workspace.snapshot().selected_paths)

    def active_file_path(self) -> str | None:
        return self.photo_workspace.snapshot().active_path

    def on_selection_changed(self) -> None:
        selected_items = self.files.selectedItems()
        current_item = self.files.currentItem()
        requested_paths = tuple(
            item.text()
            for item in ([current_item] if current_item in selected_items else [])
            + [item for item in selected_items if item is not current_item]
        )
        snapshot = self.photo_workspace.select_paths(requested_paths)
        self._selection_token += 1
        self._pending_metadata_read = None
        self._metadata_read_timer.stop()
        sel = list(snapshot.selected_paths)
        if not sel:
            self._hide_batch_overview()
            self._preview_token += 1
            self._pending_preview_load = None
            self._preview_load_timer.stop()
            self._discard_queued_previews()
            self.selectedLabel.setText("Drop JPG/JPEG files here")
            self.mutationStatusLabel.setText("")
            self.mismatchLabel.setText("")
            self.resolveBtn.setEnabled(False)
            self.keywordsList.clear()
            self.dateLabel.setText("")
            self.previewLabel.setText("No preview")
            self.previewLabel.setPixmap(QtGui.QPixmap())
            self._preview_image = None
            self.refresh_known_tags()
            return

        if len(sel) >= 2:
            self._preview_token += 1
            self._pending_preview_load = None
            self._preview_load_timer.stop()
            self._discard_queued_previews()
            self._show_batch_overview(tuple(sel))
            return

        self._hide_batch_overview()
        current = snapshot.active_path
        if current is None:
            return
        self.selectedLabel.setText(current)
        self.resolveBtn.setEnabled(False)
        self._refresh_mutation_status_view()
        self._load_preview_async(current)

        self._pending_metadata_read = (self._selection_token, current)
        self.statusBar().showMessage("Reading keywords...")
        self._schedule_pending_metadata_read()

    def _schedule_pending_metadata_read(self) -> None:
        if self._metadata_read_in_flight:
            return
        self._metadata_read_timer.start()

    def _start_pending_metadata_read(self) -> None:
        if self._metadata_read_in_flight or self._pending_metadata_read is None:
            return
        token, current = self._pending_metadata_read
        self._pending_metadata_read = None
        self._metadata_read_in_flight = True
        worker = Worker(self.exif.read_keywords, current)

        def _ok(st: KeywordState) -> None:
            self._metadata_read_in_flight = False
            if token == self._selection_token:
                self._tag_mutation_coordinator.remember_confirmed({current: st})
                displayed = self._tag_mutation_coordinator.metadata_for(current) or st
                self._keywords_cache[current] = displayed
                self._update_index_states({current: st})
                self._render_keywords(displayed)
                self._refresh_mutation_status_view()
                if st.date_display:
                    self.dateLabel.setText(f"Capture date: {st.date_display}")
                else:
                    self.dateLabel.setText("Capture date: (missing)")
                if self.statusBar().currentMessage() == "Reading keywords...":
                    self.statusBar().showMessage("Ready")
                self.refresh_known_tags()
            self._schedule_pending_metadata_read()

        def _err(msg: str) -> None:
            self._metadata_read_in_flight = False
            if token == self._selection_token and not self._queue_stale_result_repair(
                current, msg
            ):
                self.statusBar().showMessage("Error")
                self._show_error(msg, source="Read keywords")
            self._schedule_pending_metadata_read()

        worker.signals.finished.connect(_ok)
        worker.signals.error.connect(_err)
        self.pool.start(worker, METADATA_READ_PRIORITY)

    def _discard_queued_previews(self) -> None:
        for worker in self._queued_preview_workers:
            try:
                self.pool.tryTake(worker)
            except RuntimeError:
                pass
        self._queued_preview_workers.clear()

    def _forget_queued_preview(self, worker: Worker) -> None:
        try:
            self._queued_preview_workers.remove(worker)
        except ValueError:
            pass

    def _load_preview_async(self, path: str) -> None:
        self._discard_queued_previews()
        self._preview_token += 1
        self._pending_preview_load = (self._preview_token, path)
        self.previewLabel.setText("Loading preview...")
        self.previewLabel.setPixmap(QtGui.QPixmap())
        self._preview_image = None
        self._preview_load_timer.start()

    def _start_pending_preview_load(self) -> None:
        if self._pending_preview_load is None:
            return
        token, path = self._pending_preview_load
        self._pending_preview_load = None

        def _work(p: str) -> QtGui.QImage:
            reader = QtGui.QImageReader(p)
            reader.setAutoTransform(True)
            img = reader.read()
            if img.isNull():
                raise RuntimeError("Failed to load image preview")
            return img

        worker = Worker(_work, path)

        def _ok(img: QtGui.QImage) -> None:
            self._forget_queued_preview(worker)
            if token != self._preview_token:
                return
            self._preview_image = img
            self._update_preview_pixmap()
            self.previewLabel.setText("")

        def _err(msg: str) -> None:
            self._forget_queued_preview(worker)
            if token != self._preview_token:
                return
            self.previewLabel.setText("No preview")
            self.previewLabel.setPixmap(QtGui.QPixmap())
            self._preview_image = None
            self._record_session_error("Image preview", msg)

        worker.signals.finished.connect(_ok)
        worker.signals.error.connect(_err)
        self._queued_preview_workers.append(worker)
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

    def _show_batch_overview(self, selection: tuple[str, ...]) -> None:
        """Render a batch target immediately, then fill its IPTC summary off-thread."""
        self._batch_summary_generation += 1
        generation = self._batch_summary_generation
        self._batch_summary_selection = selection
        self.previewBox.hide()
        self.mutationStatusLabel.hide()
        self.mismatchLabel.hide()
        self.resolveBtn.hide()
        self.tagsOnImageLabel.hide()
        self.keywordsList.hide()
        self.removeBtn.hide()
        self.batchOverview.show()
        representatives = [f"▣ {Path(path).name}" for path in selection[:3]]
        if len(selection) > 3:
            representatives.append("▣ …")
        self.batchRepresentativeLabel.setText(
            "Representative photos:\n" + "\n".join(representatives)
        )
        self.batchCountLabel.setText(f"{len(selection)} photos selected")
        self.batchSummaryStatus.setText("Reading canonical IPTC tags…")
        self.batchSharedTagsList.clear()
        self.batchPartialTagsLabel.setText("")
        self.batchRemoveBtn.setEnabled(False)

        states: dict[str, KeywordState] = {}
        missing: list[str] = []
        for path in selection:
            state = self._tag_mutation_coordinator.metadata_for(path)
            if state is None:
                state = self._keywords_cache.get(path)
            if state is None:
                missing.append(path)
            else:
                states[path] = state
        if not missing:
            self._render_batch_summary(
                selection, summarize_batch_tags(selection, states)
            )
            return

        workspace_generation = self._tag_mutation_coordinator.workspace_generation
        worker = Worker(self.exif.read_keywords_many, missing)

        def _ok(read_states: dict[str, KeywordState]) -> None:
            if (
                generation != self._batch_summary_generation
                or selection != self._batch_summary_selection
                or workspace_generation
                != self._tag_mutation_coordinator.workspace_generation
            ):
                return
            if set(read_states) != set(missing):
                self._render_batch_summary(selection, BatchTagSummary(len(selection)))
                return
            self._tag_mutation_coordinator.remember_confirmed(read_states)
            self._keywords_cache.update(read_states)
            self._update_index_states(read_states)
            states.update(read_states)
            self._render_batch_summary(
                selection, summarize_batch_tags(selection, states)
            )

        def _err(_message: str) -> None:
            if (
                generation == self._batch_summary_generation
                and selection == self._batch_summary_selection
                and workspace_generation
                == self._tag_mutation_coordinator.workspace_generation
            ):
                self._render_batch_summary(selection, BatchTagSummary(len(selection)))

        worker.signals.finished.connect(_ok)
        worker.signals.error.connect(_err)
        self.pool.start(worker, METADATA_READ_PRIORITY)

    def _hide_batch_overview(self) -> None:
        self._batch_summary_generation += 1
        self._batch_summary_selection = ()
        self.batchOverview.hide()
        self.previewBox.show()
        self.mutationStatusLabel.show()
        self.mismatchLabel.show()
        self.resolveBtn.show()
        self.tagsOnImageLabel.show()
        self.keywordsList.show()
        self.removeBtn.show()

    def _render_batch_summary(
        self, selection: tuple[str, ...], summary: BatchTagSummary
    ) -> None:
        if selection != tuple(self.selected_file_paths()):
            return
        self.batchSharedTagsList.clear()
        if not summary.complete:
            self.batchSummaryStatus.setText(
                "Tag summary incomplete; shared-tag removal is unavailable."
            )
            self.batchPartialTagsLabel.setText("")
            self.batchRemoveBtn.setEnabled(False)
            return
        self.batchSummaryStatus.setText("")
        self.batchSharedTagsList.addItems(summary.shared_tags)
        partial = ", ".join(summary.partial_tags) or "None"
        self.batchPartialTagsLabel.setText(f"Tags on some selected photos: {partial}")
        self.batchRemoveBtn.setEnabled(bool(summary.shared_tags))

    def _refresh_batch_summary(self) -> None:
        selection = tuple(self.selected_file_paths())
        if len(selection) >= 2:
            self._show_batch_overview(selection)

    def remove_shared_batch_tag(self) -> None:
        items = self.batchSharedTagsList.selectedItems()
        if not items:
            self.statusBar().showMessage("Select a shared tag to remove")
            return
        files = self.selected_file_paths()
        if len(files) < 2:
            return
        tag = items[0].text()
        pending_mutation = self._begin_pending_tag_mutation(
            files, [TagIntent.remove(tag)]
        )
        self.statusBar().showMessage(f"Queued remove '{tag}' from {len(files)} file(s)")
        self._enqueue_tag_mutation(
            files,
            lambda paths: self.tag_mutations.remove_tags(
                paths,
                {tag.casefold()},
                keep_backup=self.keepBackup.isChecked(),
                load_state=self.exif.read_keywords,
            ),
            pending_mutation,
            f"Removed '{tag}' from {len(files)} file(s)",
        )

    def _render_keywords(self, st: KeywordState) -> None:
        self._vim_visual_keywords = False
        self.keywordsList.setSelectionMode(
            QtWidgets.QAbstractItemView.SelectionMode.SingleSelection
        )
        self.keywordsList.clear()
        reconciliation = reconcile_keywords(st)
        for keyword in reconciliation.current_tags:
            self.keywordsList.addItem(keyword)
        if self.keywordsList.count() > 0:
            self._set_single_list_selection(self.keywordsList, 0)
        if reconciliation.requires_resolution:
            self.mismatchLabel.setText(
                "IPTC:Keywords and XMP-dc:Subject need resolution"
            )
            self.resolveBtn.setEnabled(True)
        else:
            self.mismatchLabel.setText("")
            self.resolveBtn.setEnabled(False)

    def _capture_files_selection_scroll_anchor(self) -> None:
        """Capture the viewport before a Files-pane mouse selection."""
        self._files_selection_scroll_anchor = self._capture_files_scroll_anchor()

    def _schedule_files_selection_scroll_anchor_restore(self) -> None:
        """Restore after the mouse selection has queued its viewport changes."""
        if self._files_selection_scroll_anchor is not None:
            # Let the native QListWidget finish its deferred ensure-visible work
            # before restoring the pre-click viewport. A zero-delay timer can run
            # first on Windows, so the native scroll wins afterward.
            self._files_selection_scroll_restore_timer.start(1)

    def _queue_files_selection_scroll_anchor_restore(
        self, anchor: tuple[str | None, int]
    ) -> None:
        self._files_selection_scroll_anchor = anchor
        # Programmatic selection signals have returned, so zero-delay work that
        # they queued runs before this owned restoration timer.
        self._files_selection_scroll_restore_timer.start(0)

    def _restore_pending_files_selection_scroll_anchor(self) -> None:
        anchor = self._files_selection_scroll_anchor
        self._files_selection_scroll_anchor = None
        if anchor is not None:
            self._restore_files_scroll_anchor(anchor)

    def _capture_files_scroll_anchor(self) -> tuple[str | None, int]:
        viewport = self.files.viewport().rect()
        visible_items = []
        for index in range(self.files.count()):
            item = self.files.item(index)
            if item is None or item.isHidden():
                continue
            rect = self.files.visualItemRect(item)
            if rect.intersects(viewport):
                visible_items.append((rect.top(), item))
        if not visible_items:
            return None, 0
        _top, top_item = min(visible_items, key=lambda value: value[0])
        return (
            normalize_path(top_item.text()),
            self.files.visualItemRect(top_item).top(),
        )

    def _restore_files_scroll_anchor(self, anchor: tuple[str | None, int]) -> None:
        path, offset = anchor
        if path is None:
            return
        item = self._find_item_by_path(path)
        if item is None or item.isHidden():
            return
        self.files.scrollToItem(
            item, QtWidgets.QAbstractItemView.ScrollHint.PositionAtTop
        )
        scroll_bar = self.files.verticalScrollBar()
        scroll_bar.setValue(scroll_bar.value() + offset)

    def _preserve_files_scroll(self, fn) -> None:
        view = self.files
        sb = view.verticalScrollBar()
        top_path, top_offset = self._capture_files_scroll_anchor()

        fn()

        if top_path:
            item = self._find_item_by_path(top_path)
            if item is not None and not item.isHidden():
                view.scrollToItem(
                    item, QtWidgets.QAbstractItemView.ScrollHint.PositionAtTop
                )
                sb.setValue(sb.value() + top_offset)

    def apply_iptc_filter_async(self) -> None:
        """Apply the immediate SQLite IPTC-empty view without a metadata scan."""
        before = self.selected_file_paths()
        if not self.onlyUntagged.isChecked():
            prior_snapshot = self.photo_workspace.snapshot()
            snapshot = self.photo_workspace.clear_iptc_empty_filter()
            self._clear_iptc_empty_refresh_state()
            self._background_coordinator.invalidate_iptc_empty()
            self._render_photo_workspace_snapshot(
                snapshot,
                before,
                scroll_active_to_top=(
                    prior_snapshot.view_mode is PhotoWorkspaceViewMode.IPTC_EMPTY
                    and prior_snapshot.filter_operation_id is None
                ),
            )
            return

        workspace_snapshot = self.photo_workspace.snapshot()
        root = (
            self._index_root
            if workspace_snapshot.view_mode is PhotoWorkspaceViewMode.DATABASE_SEARCH
            else self._index_root_for_paths(self.all_file_paths())
        )
        if not root:
            self.onlyUntagged.blockSignals(True)
            self.onlyUntagged.setChecked(False)
            self.onlyUntagged.blockSignals(False)
            self.statusBar().showMessage("No index root available")
            return
        root = normalize_path(root)
        self._index_root = root
        self._clear_iptc_empty_refresh_state()
        self._background_coordinator.invalidate_iptc_empty()
        snapshot = self.photo_workspace.start_indexed_iptc_empty_filter()
        self._iptc_empty_root = root
        self._iptc_empty_filter_operation_id = snapshot.filter_operation_id
        self._render_photo_workspace_snapshot(snapshot, before)
        self._iptc_empty_waiting_for_index = root in self._index_sync_inflight
        if self._iptc_empty_waiting_for_index:
            self.statusBar().showMessage(
                "Waiting for index before filtering IPTC-empty…"
            )
            return
        self._iptc_empty_filter_request = self._background_coordinator.load_iptc_empty(
            root,
            workspace_snapshot.paths,
            workspace_generation=self._tag_mutation_coordinator.workspace_generation,
        )
        self.statusBar().showMessage("Filtering IPTC-empty…")

    def _render_photo_workspace_snapshot(
        self,
        snapshot: PhotoWorkspaceSnapshot,
        previous_selection: list[str],
        *,
        scroll_active_to_top: bool = False,
    ) -> bool:
        """Render a workspace transition and refresh details after selection changes."""
        self._preserve_files_scroll(lambda: self._render_photo_workspace(snapshot))
        if scroll_active_to_top and snapshot.active_path is not None:
            item = self._find_item_by_path(snapshot.active_path)
            if item is not None:
                self.files.scrollToItem(
                    item, QtWidgets.QAbstractItemView.ScrollHint.PositionAtTop
                )
        selection_changed = list(snapshot.selected_paths) != previous_selection
        if selection_changed:
            self.on_selection_changed()
            self._ensure_list_item_visible(self.files, self.files.currentItem())
        return selection_changed

    def _set_filter_chips(
        self,
        conditions: list[tuple[str, str, str]],
        excluded_directory_names: tuple[str, ...],
    ) -> None:
        """Render keyboard-removable active filter conditions in the Files pane."""
        while self.filterChipsLayout.count():
            item = self.filterChipsLayout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        if not conditions and not excluded_directory_names:
            self.filterChips.hide()
            return
        prefix = QtWidgets.QLabel("Filters:")
        prefix.setStyleSheet("color: palette(text); font-size: 11px;")
        self.filterChipsLayout.addWidget(prefix)
        for kind, label, value in conditions:
            self._add_filter_chip(kind, label, value)
        for name in excluded_directory_names:
            self._add_filter_chip("directory", f"Excluded: {name}", name)
        self.filterChips.show()

    def _add_filter_chip(self, kind: str, label: str, value: str = "") -> None:
        chip = QtWidgets.QToolButton()
        chip.setText(f"{label} ×")
        accessible_label = (
            f"Remove exclusion {value}"
            if kind == "directory"
            else f"Remove {label} filter"
        )
        chip.setAccessibleName(accessible_label)
        chip.setToolTip(accessible_label)
        chip.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Maximum,
            QtWidgets.QSizePolicy.Policy.Fixed,
        )
        chip.setStyleSheet(
            "QToolButton { background: #e7f0fa; border: 1px solid #aac5de; "
            "border-radius: 8px; color: #315e86; padding: 1px 5px; font-size: 10px; }"
        )
        chip.clicked.connect(
            lambda _checked=False, chip_kind=kind, chip_value=value: (
                self._remove_filter_chip(chip_kind, chip_value)
            )
        )
        self.filterChipsLayout.addWidget(chip)

    def _remove_filter_chip(self, kind: str, value: str) -> None:
        chips = [
            self.filterChipsLayout.itemAt(index).widget()
            for index in range(self.filterChipsLayout.count())
        ]
        focused_chip = self.focusWidget()
        chip_index = chips.index(focused_chip) if focused_chip in chips else 1
        if kind in {"tags", "date"}:
            self._clear_database_search_component(kind)
        elif kind == "filename":
            self.clear_filename_filter()
        elif kind == "iptc-empty":
            self.onlyUntagged.setChecked(False)
        elif kind == "directory":
            self.clear_directory_exclusion(value)
        QtCore.QTimer.singleShot(
            0, lambda: self._focus_filter_chip_or_files(chip_index)
        )

    def _focus_filter_chip_or_files(self, preferred_index: int) -> None:
        chips = self.filterChips.findChildren(QtWidgets.QToolButton)
        if chips:
            chips[min(preferred_index - 1, len(chips) - 1)].setFocus()
        else:
            self.files.setFocus()

    def _clear_database_search_component(self, component: str) -> None:
        if component == "tags":
            self.dbSearchEdit.clear()
        else:
            self.dbDateSearchEdit.clear()
        if self._database_search_query():
            self.apply_db_search()
        else:
            self.clear_db_search()

    def _update_view_indicator(self, snapshot: PhotoWorkspaceSnapshot) -> None:
        """Render workspace count, active filter bubbles, and the match count."""
        self.workspaceCountLabel.setText(
            f"{self.photo_workspace.workspace_path_count} in workspace"
        )
        conditions: list[tuple[str, str, str]] = []
        has_db_search = (
            self._active_search_request is not None or snapshot.has_database_search
        )
        if has_db_search:
            tag_query = self.dbSearchEdit.text().strip()
            date_query = self.dbDateSearchEdit.text().strip()
            if tag_query:
                conditions.append(("tags", f"Tags: {tag_query}", tag_query))
            if date_query:
                conditions.append(("date", f"Date: {date_query}", date_query))
        if snapshot.filename_filter_query is not None:
            conditions.append(
                ("filename", f"Filename: {snapshot.filename_filter_query}", "")
            )
        if (
            snapshot.filter_operation_id is not None
            or snapshot.view_mode is PhotoWorkspaceViewMode.IPTC_EMPTY
        ):
            conditions.append(("iptc-empty", "No tags", ""))

        self._set_filter_chips(conditions, snapshot.excluded_directory_names)
        has_conditions = bool(conditions) or bool(snapshot.excluded_directory_names)
        if self._active_search_request is not None:
            message = "Searching…"
        elif snapshot.filter_operation_id is not None:
            message = "Filtering…"
        elif has_conditions:
            message = f"match {len(snapshot.visible_paths)} files"
        else:
            message = ""
        self.filterInfoLabel.setText(message)
        self.filterInfoLabel.setVisible(bool(message))
        self.filterSummary.setVisible(has_conditions or bool(message))

    def _update_files_pane_empty_state(self, snapshot: PhotoWorkspaceSnapshot) -> None:
        """Show an unambiguous empty state for completed active conditions."""
        has_condition = (
            snapshot.filename_filter_query is not None
            or bool(snapshot.excluded_directory_names)
            or snapshot.view_mode is not PhotoWorkspaceViewMode.NORMAL
        )
        if (
            has_condition
            and not snapshot.visible_paths
            and self._active_search_request is None
            and snapshot.filter_operation_id is None
        ):
            self._show_files_pane_message("No photos match the active filters.")
            return
        if self.filesPaneMessage.text() == "No photos match the active filters.":
            self._hide_files_pane_message()

    def _refresh_current_keywords_view_from_cache(self) -> None:
        current = self.active_file_path()
        if current is None:
            return
        st = self._keywords_cache.get(current)
        if st is None:
            return
        self._render_keywords(st)
        self._refresh_mutation_status_view()
        if st.date_display:
            self.dateLabel.setText(f"Capture date: {st.date_display}")
        else:
            self.dateLabel.setText("Capture date: (missing)")

    def _begin_pending_tag_mutation(
        self, files: list[str], intents: list[TagIntent]
    ) -> PendingTagMutation | None:
        intents_by_path = {path: intents for path in files}
        active_path = self.active_file_path()
        current = normalize_path(active_path) if active_path else None
        confirmed_states: dict[str, KeywordState] = {}
        for path in files:
            if self._tag_mutation_coordinator.confirmed_for(path) is not None:
                continue
            state = self._keywords_cache.get(path)
            if state is None and current and normalize_path(path) == current:
                keywords = self._current_keywords_from_ui()
                state = KeywordState(keywords, keywords)
            if state is not None:
                confirmed_states[path] = state
        return self._tag_mutation_coordinator.begin_intents(
            intents_by_path, confirmed_states
        )

    def _handle_tag_mutation_lifecycle(self, event: TagMutationLifecycle) -> None:
        self._handle_duplicate_mutation_lifecycle(event)
        if event.kind is TagMutationLifecycleKind.DISCARDED:
            return
        if event.kind is TagMutationLifecycleKind.PENDING:
            self._keywords_cache.update(dict(event.displayed_states))
            self._refresh_file_mutation_indicators(
                [path for path, _state in event.displayed_states]
            )
            self._refresh_current_keywords_view_from_cache()
            self._refresh_batch_summary()
            return

        if event.kind is TagMutationLifecycleKind.COMPLETED:
            if event.failed_paths:
                self._record_session_error(
                    "Tag mutation",
                    f"{len(event.failed_paths)} photo(s) failed — use :retry",
                )
            confirmed_states = dict(event.confirmed_states)
            restored_states = dict(event.restored_states)
            self._iptc_empty_unknown_paths.difference_update(
                normalize_path(path)
                for path, state in confirmed_states.items()
                if state.iptc_readable
            )
            self._update_index_states(confirmed_states)
            if not event.render_workspace:
                return
            self._keywords_cache.update(confirmed_states)
            self._keywords_cache.update(restored_states)
            self._refresh_file_mutation_indicators(
                list(confirmed_states)
                + list(restored_states)
                + list(event.failed_paths)
            )
            self._refresh_current_keywords_view_from_cache()
            self._refresh_batch_summary()
            self._apply_filter_visibility_changes(dict(event.emptiness_by_path))
            if event.failed_paths:
                self.statusBar().showMessage(
                    f"{len(confirmed_states)} succeeded, "
                    f"{len(event.failed_paths)} failed — use :retry"
                )
            elif event.status_message:
                self.statusBar().showMessage(event.status_message)
            return

        restored_states = dict(event.restored_states)
        detail = event.error or "Unknown tag mutation failure"
        if not event.render_workspace:
            self._record_session_error("Tag mutation", detail)
            return
        self._keywords_cache.update(restored_states)
        self._refresh_file_mutation_indicators(list(restored_states))
        self._refresh_current_keywords_view_from_cache()
        self._refresh_batch_summary()
        self.statusBar().showMessage("Error")
        self._show_error(detail, source="Tag mutation")

    def _current_keywords_from_ui(self) -> list[str]:
        items = [self.keywordsList.item(i) for i in range(self.keywordsList.count())]
        return [
            it.text().strip() for it in items if it is not None and it.text().strip()
        ]

    def _enqueue_tag_mutation(
        self,
        paths: list[str],
        fn: Callable[[list[str]], TagMutationResult],
        pending_mutation: PendingTagMutation | None,
        status: str | None = None,
    ) -> None:
        self._tag_mutation_coordinator.enqueue(paths, fn, pending_mutation, status)

    def _find_item_by_path(self, path: str) -> QtWidgets.QListWidgetItem | None:
        return self._file_items_by_path.get(normalize_path(path))

    def _schedule_filename_filter(self, text: str) -> None:
        """Apply a non-empty filename query after the user pauses typing."""
        if not text.strip():
            self._filename_filter_timer.stop()
            if self.photo_workspace.snapshot().filename_filter_query is not None:
                self.apply_filename_filter()
            return
        self._filename_filter_timer.start()

    def _apply_filename_filter_immediately(self, _value: object = None) -> None:
        """Apply an explicit filename-filter control change without delay."""
        self._filename_filter_timer.stop()
        self.apply_filename_filter()

    def _apply_filename_filter_and_focus_first(self) -> None:
        """Commit a pending filename query before moving focus to its result."""
        self._apply_filename_filter_immediately()
        self._focus_first_visible_file()

    def apply_filename_filter(self, _value: object = None) -> None:
        """Apply the pending filename condition without background work."""
        before_snapshot = self.photo_workspace.snapshot()
        before = list(before_snapshot.selected_paths)
        if (
            before_snapshot.filename_filter_query is None
            and self.filenameFilterEdit.text().strip()
        ):
            self._filename_filter_restore_scroll = self._capture_files_scroll_anchor()
        snapshot = self.photo_workspace.set_filename_filter(
            self.filenameFilterEdit.text(),
            case_sensitive=self.filenameCaseSensitiveBtn.isChecked(),
        )
        self._render_photo_workspace_snapshot(snapshot, before)
        if (
            before_snapshot.filename_filter_query is not None
            and snapshot.filename_filter_query is None
            and self._filename_filter_restore_scroll is not None
        ):
            self._restore_files_scroll_anchor(self._filename_filter_restore_scroll)
            self._filename_filter_restore_scroll = None

    def clear_filename_filter(self) -> None:
        self.filenameFilterEdit.clear()
        if self.photo_workspace.snapshot().filename_filter_query is not None:
            self.apply_filename_filter()
        self.statusBar().showMessage("Filename filter cleared")

    def apply_directory_exclusion(self) -> None:
        """Commit the Exclude folder draft as a workspace-local condition."""
        before_snapshot = self.photo_workspace.snapshot()
        before = list(before_snapshot.selected_paths)
        try:
            snapshot = self.photo_workspace.add_directory_exclusion(
                self.directoryExcludeEdit.text()
            )
        except ValueError as error:
            self._show_directory_exclusion_error(str(error))
            return
        if (
            not before_snapshot.excluded_directory_names
            and snapshot.excluded_directory_names
        ):
            self._directory_exclusion_restore_scroll = (
                self._capture_files_scroll_anchor()
            )
        self.directoryExcludeEdit.clear()
        self._clear_directory_exclusion_error()
        self._render_photo_workspace_snapshot(snapshot, before)
        self.directoryExcludeEdit.setFocus()
        self.statusBar().showMessage("Folder exclusion applied")

    def clear_directory_exclusion(self, name: str) -> None:
        """Remove one active directory exclusion and render the new membership."""
        before_snapshot = self.photo_workspace.snapshot()
        before = list(before_snapshot.selected_paths)
        try:
            snapshot = self.photo_workspace.clear_directory_exclusion(name)
        except ValueError as error:
            self._show_directory_exclusion_error(str(error))
            return
        self._clear_directory_exclusion_error()
        self._render_photo_workspace_snapshot(snapshot, before)
        if (
            before_snapshot.excluded_directory_names
            and not snapshot.excluded_directory_names
            and self._directory_exclusion_restore_scroll is not None
        ):
            self._restore_files_scroll_anchor(self._directory_exclusion_restore_scroll)
            self._directory_exclusion_restore_scroll = None
        self.statusBar().showMessage("Folder exclusion cleared")

    def _show_directory_exclusion_error(self, message: str) -> None:
        self.directoryExcludeError.setText(message)
        self.directoryExcludeError.show()
        self.directoryExcludeEdit.setFocus()

    def _clear_directory_exclusion_error(self) -> None:
        self.directoryExcludeError.clear()
        self.directoryExcludeError.hide()

    def _discard_directory_exclusion_draft(self) -> None:
        self.directoryExcludeEdit.clear()
        self._clear_directory_exclusion_error()
        self._focus_pane_files()

    def clear_all_filters(self) -> None:
        self._filename_filter_timer.stop()
        self.dbSearchEdit.clear()
        self.dbDateSearchEdit.clear()
        self.onlyUntagged.blockSignals(True)
        self.onlyUntagged.setChecked(False)
        self.onlyUntagged.blockSignals(False)
        self.filenameFilterEdit.blockSignals(True)
        self.filenameFilterEdit.clear()
        self.filenameCaseSensitiveBtn.blockSignals(True)
        self.filenameCaseSensitiveBtn.setChecked(False)
        self.filenameCaseSensitiveBtn.blockSignals(False)
        self.filenameFilterEdit.blockSignals(False)
        self._active_search_request = None
        self._displayed_search_request = None
        self._displayed_search_generation = None
        self._displayed_search_query = None
        self._background_coordinator.invalidate_search()
        self._background_coordinator.invalidate_iptc_empty()
        self._clear_iptc_empty_refresh_state()
        self._search_restore_scroll = None
        self._filename_filter_restore_scroll = None
        self._directory_exclusion_restore_scroll = None
        self.directoryExcludeEdit.clear()
        self._clear_directory_exclusion_error()
        before = self.selected_file_paths()
        snapshot = self.photo_workspace.clear_all_filters()
        self._render_photo_workspace_snapshot(snapshot, before)
        self.statusBar().showMessage("All filters cleared")

    def clear_db_search(self) -> None:
        self.dbSearchEdit.clear()
        self.dbDateSearchEdit.clear()
        self._active_search_request = None
        self._displayed_search_request = None
        self._displayed_search_generation = None
        self._displayed_search_query = None
        self._background_coordinator.invalidate_search()
        before = self.selected_file_paths()
        had_search = self.photo_workspace.has_database_search
        snapshot = self.photo_workspace.clear_database_search()
        if had_search:
            self._tag_mutation_coordinator.replace_workspace(snapshot.paths)
            self._batch_summary_generation += 1
        selection_changed = self._render_photo_workspace_snapshot(snapshot, before)
        if had_search and self._search_restore_scroll is not None:
            self._restore_files_scroll_anchor(self._search_restore_scroll)
        self._search_restore_scroll = None
        self.statusBar().showMessage("DB search cleared")
        if not selection_changed:
            self.on_selection_changed()

    def _command_filter_files(self, args: list[str]) -> None:
        self._filename_filter_timer.stop()
        case_sensitive = bool(args and args[0] == "--case")
        if case_sensitive:
            args = args[1:]
        self.filenameCaseSensitiveBtn.blockSignals(True)
        self.filenameCaseSensitiveBtn.setChecked(case_sensitive)
        self.filenameCaseSensitiveBtn.blockSignals(False)
        self.filenameFilterEdit.blockSignals(True)
        self.filenameFilterEdit.setText(" ".join(args))
        self.filenameFilterEdit.blockSignals(False)
        self.apply_filename_filter()

    def _command_exclude_directory(self, args: list[str]) -> None:
        self.directoryExcludeEdit.setText(" ".join(args))
        self.apply_directory_exclusion()

    def _command_clear_excluded_directory(self, args: list[str]) -> None:
        if not args:
            self._show_directory_exclusion_error("Folder name required")
            return
        self.clear_directory_exclusion(" ".join(args))

    def _command_search(self, args: list[str]) -> None:
        query = " ".join(args).strip()
        if not query:
            self.statusBar().showMessage("Search query required")
            return
        if query.casefold().startswith("date:"):
            self.dbSearchEdit.clear()
            self.dbDateSearchEdit.setText(query[5:])
        else:
            self.dbDateSearchEdit.clear()
            self.dbSearchEdit.setText(query)
        self.apply_db_search()

    def _database_search_query(self) -> str:
        """Translate the separate Tags and Date controls to the index grammar."""
        tag_query = self.dbSearchEdit.text().strip()
        date_query = self.dbDateSearchEdit.text().strip()
        if not date_query:
            return tag_query
        if not tag_query:
            return f"date:{date_query}"
        tag_term = (
            tag_query[4:].strip()
            if tag_query.casefold().startswith("tag:")
            else tag_query
        )
        return f"tag:{tag_term} date:{date_query}"

    def apply_db_search(self) -> None:
        query = self._database_search_query()
        if not query:
            self.clear_db_search()
            return
        try:
            validate_search_query(query)
        except DateQueryError as error:
            self.statusBar().showMessage(f"Invalid date query: {error}")
            return
        root = self._index_root_for_paths(self.all_file_paths())
        if not root:
            self.statusBar().showMessage("No index root available")
            return
        self._index_root = root
        self._active_search_request = self._background_coordinator.search_index(
            root,
            query,
            workspace_generation=self._tag_mutation_coordinator.workspace_generation,
        )
        self._update_view_indicator(self.photo_workspace.snapshot())
        self.statusBar().showMessage("Searching index…")

    def _queue_stale_result_repair(self, path: str, error: str) -> bool:
        """Queue index repair only for a confirmed missing active search result."""
        if not _MISSING_FILE_ERROR.search(error):
            return False
        try:
            if Path(path).exists():
                return False
        except OSError:
            return False

        request = self._displayed_search_request
        snapshot = self.photo_workspace.snapshot()
        if (
            request is None
            or self._active_search_request is not None
            or snapshot.view_mode is not PhotoWorkspaceViewMode.DATABASE_SEARCH
            or snapshot.active_path != path
            or request.root != self._index_root
            or self._displayed_search_generation
            != self._tag_mutation_coordinator.workspace_generation
        ):
            return False

        repair = self._background_coordinator.repair_stale_search_result(
            request.root,
            path,
            workspace_generation=self._displayed_search_generation,
            query=request.query or "",
        )
        if repair is not None:
            self._stale_result_repairs[repair.root] = repair
            self.indexRepairStatusLabel.setText(
                "Index repair queued: removing missing search result…"
            )
        return True

    def _apply_db_search_result(self, matches: tuple[str, ...]) -> None:
        before = self.selected_file_paths()
        prior_snapshot = self.photo_workspace.snapshot()
        iptc_empty_active = (
            self._iptc_empty_filter_request is not None
            or prior_snapshot.view_mode is PhotoWorkspaceViewMode.IPTC_EMPTY
        )
        if not iptc_empty_active:
            self._clear_iptc_empty_refresh_state()
            self._background_coordinator.invalidate_iptc_empty()
        first_search = not self.photo_workspace.has_database_search
        if first_search:
            self._search_restore_scroll = self._capture_files_scroll_anchor()
        snapshot = self.photo_workspace.apply_database_search_matches(
            normalize_path(path) for path in matches
        )
        self._tag_mutation_coordinator.replace_workspace(snapshot.paths)
        self._batch_summary_generation += 1
        self._render_photo_workspace_snapshot(snapshot, before)
        if snapshot.active_path is not None:
            self.files.setFocus()
        self.statusBar().showMessage(f"DB search: {len(matches)} match(es)")

    def _apply_filter_visibility_changes(
        self, emptiness_by_path: dict[str, bool]
    ) -> None:
        """Render filter facts accepted by the workspace after a tag mutation."""
        if (
            self.photo_workspace.snapshot().view_mode
            is not PhotoWorkspaceViewMode.IPTC_EMPTY
        ):
            return
        before = self.selected_file_paths()
        snapshot = self.photo_workspace.apply_iptc_emptiness(emptiness_by_path)
        self._render_photo_workspace_snapshot(snapshot, before)

    def _report_keyword_limit_violation(self, value: str, byte_count: int) -> None:
        self.statusBar().showMessage(
            f"IPTC keyword is {byte_count}/64 UTF-8 bytes: {value!r}"
        )

    def _update_add_keyword_limit_feedback(self, raw_text: str) -> None:
        violation = keyword_length_violation(raw_text)
        invalid = violation is not None
        self.addEdit.setProperty("keywordLengthInvalid", invalid)
        self.addEdit.style().unpolish(self.addEdit)
        self.addEdit.style().polish(self.addEdit)
        self.addBtn.setEnabled(not invalid)
        if violation is not None:
            self._report_keyword_limit_violation(
                violation.value, violation.utf8_byte_count
            )
        elif self.statusBar().currentMessage().startswith("IPTC keyword is "):
            self.statusBar().clearMessage()

    def _reject_invalid_iptc_keywords(self, values: list[str]) -> bool:
        violation = iptc_keyword_list_violation(values)
        if violation is None:
            return False
        self._report_keyword_limit_violation(violation.value, violation.utf8_byte_count)
        return True

    def add_keyword_from_input(self) -> None:
        raw_tag = self.addEdit.text()
        if self._reject_invalid_iptc_keywords([raw_tag]):
            self.addEdit.setFocus()
            return
        tag = normalize_keyword(raw_tag)
        if not tag:
            return
        if self._apply_add_tag(tag):
            self.addEdit.clear()

    def _apply_add_tag(self, tag: str) -> bool:
        if self._reject_invalid_iptc_keywords([tag]):
            return False
        files = self.selected_file_paths()
        if not files:
            self.statusBar().showMessage("No files selected")
            return False
        pending_mutation = self._begin_pending_tag_mutation(files, [TagIntent.add(tag)])
        add_recent_tag(tag)
        self._recent_tags_snapshot = dedupe_casefold(
            [tag] + self._recent_tags_snapshot
        )[:100]
        self.statusBar().showMessage(f"Queued add '{tag}' to {len(files)} file(s)")
        self._enqueue_tag_mutation(
            files,
            lambda paths: self.tag_mutations.add_tag(
                paths,
                tag,
                keep_backup=self.keepBackup.isChecked(),
                load_state=self.exif.read_keywords,
            ),
            pending_mutation,
            f"Added '{tag}' to {len(files)} file(s)",
        )
        return True

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
        pending_mutation = self._begin_pending_tag_mutation(
            files, [TagIntent.remove(tag) for tag in remove]
        )
        self.statusBar().showMessage(
            f"Queued remove {len(remove)} tag(s) from {len(files)} file(s)"
        )
        self._enqueue_tag_mutation(
            files,
            lambda paths: self.tag_mutations.remove_tags(
                paths,
                remove,
                keep_backup=self.keepBackup.isChecked(),
                load_state=self.exif.read_keywords,
            ),
            pending_mutation,
            f"Removed {len(remove)} tag(s) from {len(files)} file(s)",
        )

    def retry_failed_tag_mutations(self) -> None:
        self._retry_failed_tag_mutations(self.selected_file_paths(), "selected photos")

    def retry_all_failed_tag_mutations(self) -> None:
        self._retry_failed_tag_mutations(self.all_file_paths(), "the Photo Workspace")

    def _retry_failed_tag_mutations(self, paths: list[str], scope: str) -> None:
        retry = self._tag_mutation_coordinator.retry_failed(paths)
        if retry is None:
            self.statusBar().showMessage(f"No failed tag changes for {scope}")
            return
        retry_paths = list(retry.intents_by_path)
        self.statusBar().showMessage(
            f"Retrying tag changes for {len(retry_paths)} photo(s)"
        )
        self._enqueue_tag_mutation(
            retry_paths,
            lambda paths: self.tag_mutations.replace_keyword_states(
                paths,
                keep_backup=self.keepBackup.isChecked(),
                load_state=self.exif.read_keywords,
                transform=lambda path, state: retry.apply(path, state),
            ),
            retry,
            f"Retried tag changes for {len(retry_paths)} photo(s)",
        )

    def cancel_active_refresh(self) -> None:
        root = self._index_root
        if root is None or self._active_index_refresh_request is None:
            self.statusBar().showMessage("No active index refresh")
            return
        self._background_coordinator.cancel_refresh(root)
        self._active_index_refresh_request = None
        self._iptc_empty_refresh_available = False
        self._iptc_empty_refresh_check_request = None
        self.iptcEmptyRefreshOffer.hide()
        self.indexRepairStatusLabel.setText("Cancelling index refresh…")

    def reindex_active_root(self) -> None:
        root = self._index_root
        if not root:
            self.statusBar().showMessage("No active index root")
            return
        self._active_index_refresh_request = self._background_coordinator.reindex(
            root,
            workspace_generation=self._tag_mutation_coordinator.workspace_generation,
        )
        self.statusBar().showMessage("Reindexing photos…")

    def refresh_iptc_empty_view(self) -> None:
        """Explicitly apply a post-update SQLite IPTC-empty result when offered."""
        root = self._iptc_empty_root
        if (
            root is None
            or not self._iptc_empty_refresh_available
            or not self._has_current_iptc_empty_view(root)
        ):
            self.statusBar().showMessage("No IPTC-empty results to refresh")
            return
        self._iptc_empty_refresh_available = False
        self.iptcEmptyRefreshOffer.hide()
        self._iptc_empty_refresh_apply_request = self._background_coordinator.load_iptc_empty(
            root,
            self.photo_workspace.snapshot().paths,
            workspace_generation=self._tag_mutation_coordinator.workspace_generation,
        )
        self.statusBar().showMessage("Refreshing IPTC-empty results…")

    def force_refresh_known_tags(self) -> None:
        """Refresh the cached autocomplete vocabulary for the active index root."""
        snapshot = self.photo_workspace.snapshot()
        paths = self.selected_file_paths() or self.all_file_paths()
        root = (
            self._iptc_empty_root
            if snapshot.view_mode is PhotoWorkspaceViewMode.IPTC_EMPTY
            else self._index_root_for_paths(paths)
            if paths
            else None
        )
        if not root:
            return
        self._index_root = root
        self._active_known_tags_request = self._background_coordinator.load_known_tags(
            root,
            workspace_generation=self._tag_mutation_coordinator.workspace_generation,
        )

    def refresh_known_tags(self) -> None:
        """Refresh cached autocomplete candidates when the workspace root changes."""
        paths = self.selected_file_paths() or self.all_file_paths()
        root = self._index_root_for_paths(paths) if paths else None
        if root and normalize_path(root) != self._known_tags_root:
            self.force_refresh_known_tags()

    def _known_tag_candidates(self) -> list[str]:
        """Return deduplicated recent and indexed tags for add-tag autocomplete."""
        return sorted(
            dedupe_casefold(
                self._recent_tags_snapshot
                + sorted(self._known_tags_snapshot, key=str.casefold)
            ),
            key=str.casefold,
        )

    def toggle_files_filter_block(self) -> None:
        """Toggle session-local Files-pane filter input visibility."""
        show_filters = not self.filesFilterBox.isVisible()
        focus = self.focusWidget()
        if (
            not show_filters
            and focus is not None
            and self.filesFilterBox.isAncestorOf(focus)
        ):
            self.files.setFocus()
        self.filesFilterBox.setVisible(show_filters)
        arrow = (
            QtCore.Qt.ArrowType.DownArrow
            if show_filters
            else QtCore.Qt.ArrowType.RightArrow
        )
        action = "Hide filters" if show_filters else "Show filters"
        self.filesFilterToggleBtn.setArrowType(arrow)
        self.filesFilterToggleBtn.setToolTip(action)
        self.filesFilterToggleBtn.setAccessibleName(action)

    def _show_files_filter_block(self) -> None:
        if not self.filesFilterBox.isVisible():
            self.toggle_files_filter_block()

    def _focus_db_search_select_all(self) -> None:
        self._show_files_filter_block()
        self.dbSearchEdit.setFocus()
        self.dbSearchEdit.selectAll()

    def _focus_date_filter_select_all(self) -> None:
        self._show_files_filter_block()
        self.dbDateSearchEdit.setFocus()
        self.dbDateSearchEdit.selectAll()

    def _toggle_filename_case_sensitive(self) -> None:
        self.filenameCaseSensitiveBtn.toggle()

    def _focus_filename_filter_select_all(self) -> None:
        self._show_files_filter_block()
        self.filenameFilterEdit.setFocus()
        self.filenameFilterEdit.selectAll()

    def _focus_excluded_directory_select_all(self) -> None:
        self._show_files_filter_block()
        self.directoryExcludeEdit.setFocus()
        self.directoryExcludeEdit.selectAll()

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

    def _record_session_error(self, source: str, detail: str) -> None:
        self._error_history.record(source, detail)

    def show_error_history(self) -> None:
        entries = self._error_history.entries()
        if not entries:
            text = "No errors in this session."
        else:
            text = "\n".join(
                f"{entry.timestamp} — {entry.source}: {entry.detail}"
                for entry in entries
            )
        QtWidgets.QMessageBox.information(self, "Errors", text)

    def _show_error(self, msg: str, *, source: str = "TAGGER") -> None:
        self._record_session_error(source, msg)
        QtWidgets.QMessageBox.critical(self, "Error", msg)

    def resolve_mismatch(self) -> None:
        path = self.active_file_path()
        if path is None:
            self.statusBar().showMessage("No active photo")
            return
        state = self._keywords_cache.get(path)
        if state is None:
            self.statusBar().showMessage("Keywords are still loading")
            return
        if not reconcile_keywords(state).requires_resolution:
            self.statusBar().showMessage("No IPTC/XMP resolution is needed")
            return

        dialog = ResolveKeywordsDialog(state, self)
        if dialog.exec() != QtWidgets.QDialog.DialogCode.Accepted:
            return
        chosen = dialog.chosen_state()
        pending_mutation = self._begin_pending_tag_mutation(
            [path], [TagIntent.replace_fields(chosen)]
        )
        self.statusBar().showMessage("Saving IPTC/XMP resolution…")
        self._enqueue_tag_mutation(
            [path],
            lambda paths: self.tag_mutations.resolve_keyword_fields(
                paths,
                {path: chosen},
                keep_backup=self.keepBackup.isChecked(),
                load_state=self.exif.read_keywords,
            ),
            pending_mutation,
            "Resolved IPTC/XMP keywords",
        )

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
            self._show_error(msg, source="Copy EXIF date")

        worker.signals.finished.connect(_ok)
        worker.signals.error.connect(_err)
        self.pool.start(worker)
