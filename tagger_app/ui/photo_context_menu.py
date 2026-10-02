"""Shared photo menu presentation; each caller binds its own action targets."""

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from PyQt6 import QtWidgets


@dataclass(frozen=True)
class PhotoContextActions:
    open_photo: Callable[[], None]
    open_gimp: Callable[[], None]
    copy_path: Callable[[], None]
    reveal_photo: Callable[[], None]
    exclude_folder: Callable[[str], None]


def build_photo_context_menu(
    parent: QtWidgets.QWidget, path: str, actions: PhotoContextActions
) -> QtWidgets.QMenu:
    menu = QtWidgets.QMenu(parent)
    menu.setToolTipsVisible(True)
    menu.addAction("Open", actions.open_photo)
    menu.addAction("Open in GIMP", actions.open_gimp)
    menu.addAction("Copy file path", actions.copy_path)
    menu.addAction("Reveal in Explorer", actions.reveal_photo)
    directory_name = Path(path).parent.name
    if directory_name:
        exclude = menu.addAction(
            f'Exclude folders named "{directory_name}"',
            lambda: actions.exclude_folder(directory_name),
        )
        exclude.setToolTip(
            "Exclude this folder name from the tagging Photo Workspace; "
            "duplicate scan findings are unchanged."
        )
    return menu
