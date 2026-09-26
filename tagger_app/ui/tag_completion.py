"""Explicit, keyboard-driven tag completion; never submits a tag mutation."""

from collections.abc import Callable

from PyQt6 import QtCore, QtGui, QtWidgets


class TagCompletion(QtWidgets.QFrame):
    def __init__(
        self,
        edit: QtWidgets.QLineEdit,
        candidates: Callable[[str], list[str]],
        parent: QtWidgets.QWidget,
    ) -> None:
        super().__init__(parent)
        self.edit = edit
        self.candidates = candidates
        self.matches: list[str] = []
        self.selected = 0
        self.buttons: list[QtWidgets.QPushButton] = []
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(3, 2, 3, 2)
        layout.setSpacing(1)
        self.counter = QtWidgets.QLabel()
        layout.addWidget(self.counter)
        self.scroll = QtWidgets.QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        self.scroll.setVerticalScrollBarPolicy(
            QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.scroll.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        layout.addWidget(self.scroll)
        self.setStyleSheet(
            "TagCompletion { background: palette(window); border: 1px solid palette(mid); }"
            "QPushButton { padding: 1px 5px; border: 1px solid palette(mid); border-radius: 3px; }"
            "QPushButton:checked { background: palette(highlight); color: palette(highlighted-text); }"
        )
        self.scroll.horizontalScrollBar().valueChanged.connect(self._counter)
        self.scroll.horizontalScrollBar().rangeChanged.connect(self._counter)
        self.edit.textChanged.connect(self._edited)
        self.hide()

    def _edited(self) -> None:
        if self.isVisible():
            self._refresh()

    def _refresh(self) -> None:
        query = self.edit.text().strip()
        self.matches = self.candidates(query) if query else []
        self.selected = 0
        if not self.matches:
            self.hide()
            return
        row = QtWidgets.QWidget(self.scroll)
        layout = QtWidgets.QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(3)
        layout.setSizeConstraint(QtWidgets.QLayout.SizeConstraint.SetMinimumSize)
        self.buttons = []
        for index, text in enumerate(self.matches):
            button = QtWidgets.QPushButton(text.replace("&", "&&"), row)
            button.setCheckable(True)
            button.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
            button.setFixedWidth(button.sizeHint().width())
            button.clicked.connect(lambda _checked, i=index: self._select(i))
            layout.addWidget(button)
            self.buttons.append(button)
        layout.addStretch()
        self.scroll.setWidget(row)
        self.scroll.setFixedHeight(
            row.sizeHint().height()
            + self.scroll.horizontalScrollBar().sizeHint().height()
            + 2
        )
        self.show()
        self.reposition()
        self.raise_()
        self._select(0)

    def complete(self) -> None:
        if not self.isVisible():
            query = self.edit.text().strip()
            matches = self.candidates(query) if query else []
            if len(matches) == 1:
                self.edit.setText(matches[0])
                self.edit.setCursorPosition(len(matches[0]))
            else:
                self._refresh()
            return
        # Narrowing extends only the shared prefix; otherwise Tab cycles.
        prefix = self.matches[0]
        for match in self.matches[1:]:
            while not match.casefold().startswith(prefix.casefold()):
                prefix = prefix[:-1]
        if len(prefix) > len(self.edit.text().strip()):
            self.edit.setText(prefix)
            self.edit.setCursorPosition(len(prefix))
        else:
            self._select(self.selected + 1)

    def handle_event(self, event: QtCore.QEvent) -> bool:
        if event.type() == QtCore.QEvent.Type.FocusOut:
            self.hide()
        if not self.isVisible() or not isinstance(event, QtGui.QKeyEvent):
            return False
        modifiers = event.modifiers() & ~QtCore.Qt.KeyboardModifier.KeypadModifier
        if modifiers != QtCore.Qt.KeyboardModifier.NoModifier:
            return False
        key = event.key()
        keys = (
            QtCore.Qt.Key.Key_Left,
            QtCore.Qt.Key.Key_Right,
            QtCore.Qt.Key.Key_Return,
            QtCore.Qt.Key.Key_Enter,
        )
        if key not in keys:
            return False
        if event.type() == QtCore.QEvent.Type.ShortcutOverride:
            event.accept()
            return True
        if event.type() != QtCore.QEvent.Type.KeyPress:
            return False
        if key in (QtCore.Qt.Key.Key_Return, QtCore.Qt.Key.Key_Enter):
            text = self.matches[self.selected]
            self.hide()
            self.edit.setText(text)
            self.edit.setCursorPosition(len(text))
        else:
            self._select(self.selected + (1 if key == QtCore.Qt.Key.Key_Right else -1))
        event.accept()
        return True

    def _select(self, index: int) -> None:
        self.selected = index % len(self.matches)
        for i, button in enumerate(self.buttons):
            button.setChecked(i == self.selected)
        self._counter()
        QtCore.QTimer.singleShot(0, self._reveal)

    def _reveal(self) -> None:
        if self.isVisible() and self.buttons:
            self.scroll.ensureWidgetVisible(self.buttons[self.selected], 8, 0)
            self._counter()

    def _counter(self, *_args: int) -> None:
        bar = self.scroll.horizontalScrollBar()
        left = "◀ " if bar.value() > bar.minimum() else ""
        right = " ▶" if bar.value() < bar.maximum() else ""
        self.counter.setText(f"{left}{self.selected + 1} / {len(self.matches)}{right}")

    def reposition(self) -> None:
        if not self.isVisible():
            return
        pos = self.edit.mapTo(self.parentWidget(), QtCore.QPoint())
        height = self.sizeHint().height()
        self.setGeometry(
            pos.x(), max(0, pos.y() - height - 4), self.edit.width(), height
        )
        QtCore.QTimer.singleShot(0, self._reveal)
