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
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        details = QtWidgets.QWidget()
        details_layout = QtWidgets.QVBoxLayout(details)
        for text in (
            f"Source: {plan.source}",
            "Canonical tags: " + ", ".join(plan.tags),
            "Targets:\n" + "\n".join(plan.targets),
            "Backup: " + ("on" if plan.keep_backup else "off"),
            "Copy (y) confirms; Cancel (n / Esc) makes no changes.",
        ):
            label = QtWidgets.QLabel(text)
            label.setWordWrap(True)
            label.setTextFormat(QtCore.Qt.TextFormat.PlainText)
            details_layout.addWidget(label)
        scroll.setWidget(details)
        layout.addWidget(scroll, 1)
        self.resize(640, 420)
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
