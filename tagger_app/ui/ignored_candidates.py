"""Read-only inspection with separate, explicit recovery actions."""

from collections.abc import Callable
from pathlib import Path

from PyQt6 import QtCore, QtGui, QtWidgets

from tagger_app.services.ignored_candidates import (
    IgnoredCandidate,
    IgnoredCandidateStore,
)


class _VisibleShortcutStyle(QtWidgets.QProxyStyle):
    def styleHint(self, hint, option=None, widget=None, returnData=None):
        if hint == QtWidgets.QStyle.StyleHint.SH_UnderlineShortcut:
            return 1
        return super().styleHint(hint, option, widget, returnData)


class IgnoredCandidatesDialog(QtWidgets.QDialog):
    previewReady = QtCore.pyqtSignal(object)

    def __init__(
        self,
        parent,
        store: IgnoredCandidateStore,
        run_io: Callable,
        runner,
        restored: Callable,
        selected: str | None = None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Ignored candidates")
        self.setWindowModality(QtCore.Qt.WindowModality.WindowModal)
        self.resize(850, 620)
        self.store = store
        self.run_io = run_io
        self.runner = runner
        self.restored = restored
        self.selected = selected
        self.records: tuple[IgnoredCandidate, ...] = ()
        self._generation = 0
        self._closed = False
        self.finished.connect(self._close)
        self.previewReady.connect(self._preview_ready)
        layout = QtWidgets.QVBoxLayout(self)
        splitter = QtWidgets.QSplitter()
        self.candidates = QtWidgets.QListWidget()
        self.candidates.setMinimumWidth(220)
        self.candidates.setToolTip(
            "Select candidates with j / k; restore the selected candidate with r"
        )
        self.candidates.currentRowChanged.connect(self._inspect)
        splitter.addWidget(self.candidates)
        self.details = QtWidgets.QScrollArea()
        self.details.setWidgetResizable(True)
        splitter.addWidget(self.details)
        splitter.setStretchFactor(1, 1)
        layout.addWidget(splitter)
        self.message = QtWidgets.QLabel("Loading…")
        self.message.setTextFormat(QtCore.Qt.TextFormat.PlainText)
        self.message.setWordWrap(True)
        layout.addWidget(self.message)
        actions = QtWidgets.QHBoxLayout()
        self.restore = QtWidgets.QPushButton("&Restore")
        self.restore.setToolTip(
            "Restore this candidate (r); matching candidates become eligible for review"
        )
        self.restore.clicked.connect(self._restore)
        actions.addWidget(self.restore)
        self.clear = QtWidgets.QPushButton("Clear &all ignores…")
        self.clear.setToolTip(
            "Restore all ignored candidates for this index (a); confirmation required"
        )
        self.clear.clicked.connect(self._clear)
        actions.addWidget(self.clear)
        actions.addStretch()
        close = QtWidgets.QPushButton("&Close")
        close.setToolTip("Close Ignored candidates (c / Esc)")
        close.clicked.connect(self.reject)
        actions.addWidget(close)
        # Windows normally hides mnemonic underlines until Alt is pressed.
        self._shortcut_style = _VisibleShortcutStyle()
        self._shortcut_style.setParent(self)
        for button in (self.restore, self.clear, close):
            button.setStyle(self._shortcut_style)
        layout.addLayout(actions)
        self._shortcuts = []
        for key, handler in (
            ("j", lambda: self._move_selection(1)),
            ("k", lambda: self._move_selection(-1)),
            ("r", self.restore.click),
            ("a", self.clear.click),
            ("c", close.click),
        ):
            shortcut = QtGui.QShortcut(QtGui.QKeySequence(key), self)
            shortcut.setContext(QtCore.Qt.ShortcutContext.WindowShortcut)
            shortcut.activated.connect(handler)
            self._shortcuts.append(shortcut)
        self._load()

    def _move_selection(self, delta):
        if not self.candidates.isEnabled() or not self.candidates.count():
            return
        row = self.candidates.currentRow()
        row = 0 if row < 0 else max(0, min(row + delta, self.candidates.count() - 1))
        self.candidates.setCurrentRow(row)
        self.candidates.scrollToItem(self.candidates.currentItem())
        self.candidates.setFocus()

    def _set_busy(self, busy):
        self.restore.setEnabled(not busy and self.candidates.currentRow() >= 0)
        self.clear.setEnabled(not busy and bool(self.records))
        self.candidates.setEnabled(not busy)

    def _load(self):
        self._set_busy(True)
        self.run_io(self.store.list, self._loaded, self._failed)

    def _loaded(self, records):
        if self._closed:
            return
        self.records = records
        self.candidates.clear()
        for record in records:
            member = record.group.members[0]
            item = QtWidgets.QListWidgetItem(
                f"{member.timestamp}\n{len(record.group.members)} photos · {Path(member.path).name}"
            )
            item.setToolTip(
                "\n".join(member.path for member in record.group.members)
                + "\nSelect: j / k · Restore: r"
            )
            self.candidates.addItem(item)
        row = next(
            (i for i, record in enumerate(records) if record.identity == self.selected),
            0,
        )
        self.candidates.setCurrentRow(row if records else -1)
        self.message.setText(
            f"{len(records)} ignored candidates" if records else "No ignored candidates"
        )
        self._set_busy(False)

    def _failed(self, error):
        if self._closed:
            return
        self.message.setText(f"Could not update ignored candidates: {error}")
        self._set_busy(False)

    def _inspect(self, row):
        self._generation += 1
        generation = self._generation
        body = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(body)
        old = self.details.takeWidget()
        if old is not None:
            old.deleteLater()
        self.details.setWidget(body)
        self.restore.setEnabled(row >= 0 and self.candidates.isEnabled())
        if not 0 <= row < len(self.records):
            return
        record = self.records[row]
        method = QtWidgets.QLabel(f"Method: {record.detector_id}")
        method.setTextFormat(QtCore.Qt.TextFormat.PlainText)
        layout.addWidget(method)
        for member in record.group.members:
            card = QtWidgets.QGroupBox()
            card_layout = QtWidgets.QVBoxLayout(card)
            preview = QtWidgets.QLabel("Loading preview…")
            preview.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            preview.setMinimumHeight(160)
            card_layout.addWidget(preview)
            tags = ", ".join(member.iptc_tags) if member.iptc_readable else "Unknown"
            evidence = QtWidgets.QLabel(
                f"{member.path}\n{member.source_field}: {member.timestamp}\nTags when ignored: {tags or 'None'}"
            )
            evidence.setTextFormat(QtCore.Qt.TextFormat.PlainText)
            evidence.setTextInteractionFlags(
                QtCore.Qt.TextInteractionFlag.TextSelectableByMouse
            )
            evidence.setWordWrap(True)
            card_layout.addWidget(evidence)
            layout.addWidget(card)

            def load_preview(path=member.path, label=preview):
                if self._closed or generation != self._generation:
                    return
                reader = QtGui.QImageReader(path)
                reader.setAutoTransform(True)
                image = reader.read().scaled(
                    420,
                    240,
                    QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                    QtCore.Qt.TransformationMode.SmoothTransformation,
                )
                if not self._closed:
                    self.previewReady.emit((generation, label, image))

            self.runner.submit(load_preview)
        layout.addStretch()

    def _close(self):
        self._closed = True
        self._generation += 1
        self.deleteLater()

    def _preview_ready(self, data):
        generation, label, image = data
        if generation != self._generation or not self.isVisible():
            return
        if image.isNull():
            label.setText("Preview unavailable")
        else:
            label.setPixmap(QtGui.QPixmap.fromImage(image))

    def _restore(self):
        row = self.candidates.currentRow()
        if not 0 <= row < len(self.records):
            return
        identity = self.records[row].identity
        self._set_busy(True)

        def work():
            self.store.restore(identity)
            return self.store.list()

        def ready(records):
            self.restored({identity})
            self._loaded(records)

        self.run_io(work, ready, self._failed)

    def _clear(self):
        if (
            QtWidgets.QMessageBox.question(
                self,
                "Clear all ignores",
                "Restore all ignored candidates for this index?",
                defaultButton=QtWidgets.QMessageBox.StandardButton.No,
            )
            != QtWidgets.QMessageBox.StandardButton.Yes
        ):
            return
        self._set_busy(True)
        identities = {record.identity for record in self.records}

        def work():
            self.store.clear()
            return self.store.list()

        def ready(records):
            self.restored(identities)
            self._loaded(records)

        self.run_io(work, ready, self._failed)
