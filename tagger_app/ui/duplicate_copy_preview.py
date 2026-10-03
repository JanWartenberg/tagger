"""Explicit confirmation of an immutable duplicate tag-copy plan."""

from PyQt6 import QtCore, QtGui, QtWidgets

from tagger_app.services.tag_propagation import TagPropagationPlan


class DuplicateCopyPreview(QtWidgets.QDialog):
    def __init__(self, plan: TagPropagationPlan, parent: QtWidgets.QWidget) -> None:
        super().__init__(parent)
        self.setObjectName("duplicateCopyPreview")
        self.setWindowTitle("Confirm tag copy")
        self.setModal(True)
        layout = QtWidgets.QVBoxLayout(self)
        comparison = QtWidgets.QHBoxLayout()
        self.images: dict[str, QtWidgets.QLabel] = {}
        source = self._photo_column(
            "Source", plan.source, ", ".join(plan.tags), "Source"
        )
        source_scroll = QtWidgets.QScrollArea()
        source_scroll.setWidgetResizable(True)
        source_scroll.setWidget(source)
        comparison.addWidget(source_scroll, 1)
        targets = QtWidgets.QWidget()
        targets_layout = QtWidgets.QVBoxLayout(targets)
        targets_layout.setContentsMargins(0, 0, 0, 0)
        for position, path in enumerate(plan.targets, start=1):
            title = (
                "Target"
                if len(plan.targets) == 1
                else f"Target {position} of {len(plan.targets)}"
            )
            targets_layout.addWidget(
                self._photo_column(
                    title, path, "No tags → " + ", ".join(plan.tags), "Target"
                )
            )
        targets_layout.addStretch(1)
        target_scroll = QtWidgets.QScrollArea()
        target_scroll.setWidgetResizable(True)
        target_scroll.setWidget(targets)
        comparison.addWidget(target_scroll, 1)
        layout.addLayout(comparison, 1)
        backup = QtWidgets.QLabel("Backup: " + ("on" if plan.keep_backup else "off"))
        backup.setTextFormat(QtCore.Qt.TextFormat.PlainText)
        layout.addWidget(backup)
        self.resize(800, 520)
        buttons = QtWidgets.QDialogButtonBox()
        confirm = buttons.addButton(
            "Copy (y)", QtWidgets.QDialogButtonBox.ButtonRole.AcceptRole
        )
        cancel = buttons.addButton(
            "Cancel (n / Esc)", QtWidgets.QDialogButtonBox.ButtonRole.RejectRole
        )
        assert confirm is not None and cancel is not None
        confirm.setDefault(False)
        confirm.setAutoDefault(False)
        cancel.setDefault(True)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _photo_column(
        self, title: str, path: str, tags: str, role: str
    ) -> QtWidgets.QWidget:
        column = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(column)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)
        heading = QtWidgets.QLabel(title)
        heading.setTextFormat(QtCore.Qt.TextFormat.PlainText)
        layout.addWidget(heading)
        image = QtWidgets.QLabel("Loading preview…")
        image.setObjectName(f"copy{role}Image")
        image.setTextFormat(QtCore.Qt.TextFormat.PlainText)
        image.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        image.setFixedHeight(180)
        image.setMinimumWidth(0)
        image.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Ignored, QtWidgets.QSizePolicy.Policy.Fixed
        )
        self.images[path] = image
        layout.addWidget(image)
        tag_label = QtWidgets.QLabel(tags)
        tag_label.setObjectName(f"copy{role}Tags")
        tag_label.setTextFormat(QtCore.Qt.TextFormat.PlainText)
        tag_label.setWordWrap(True)
        font = tag_label.font()
        font.setBold(True)
        tag_label.setFont(font)
        layout.addWidget(tag_label)
        path_label = QtWidgets.QLabel(path)
        path_label.setTextFormat(QtCore.Qt.TextFormat.PlainText)
        path_label.setWordWrap(True)
        path_label.setTextInteractionFlags(
            QtCore.Qt.TextInteractionFlag.TextSelectableByMouse
        )
        layout.addWidget(path_label)
        return column

    def keyPressEvent(self, a0: QtGui.QKeyEvent | None) -> None:
        event = a0
        if (
            event is not None
            and event.modifiers() == QtCore.Qt.KeyboardModifier.NoModifier
        ):
            if event.key() == QtCore.Qt.Key.Key_Y:
                self.accept()
                return
            if event.key() in (QtCore.Qt.Key.Key_N, QtCore.Qt.Key.Key_Escape):
                self.reject()
                return
        super().keyPressEvent(event)
