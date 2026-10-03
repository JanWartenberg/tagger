"""Horizontal candidate strip with space reserved for content and scrolling."""

from PyQt6 import QtCore, QtWidgets


class CandidateQueue(QtWidgets.QScrollArea):
    """Keep the entire card height visible, including after font/style changes."""

    def setWidget(self, widget: QtWidgets.QWidget) -> None:
        super().setWidget(widget)
        widget.installEventFilter(self)
        self._fit_height()

    def eventFilter(self, watched: QtCore.QObject, event: QtCore.QEvent) -> bool:
        if watched is self.widget() and event.type() in (
            QtCore.QEvent.Type.LayoutRequest,
            QtCore.QEvent.Type.Resize,
        ):
            self._fit_height()
        return super().eventFilter(watched, event)

    def _fit_height(self) -> None:
        body = self.widget()
        if body is None:
            return
        # Reserve scrollbar space even without overflow to avoid layout jumps.
        height = (
            body.sizeHint().height()
            + 2 * self.frameWidth()
            + self.horizontalScrollBar().sizeHint().height()
        )
        if self.minimumHeight() != height or self.maximumHeight() != height:
            self.setFixedHeight(height)
