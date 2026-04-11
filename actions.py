from dataclasses import dataclass
from typing import Literal

from PyQt6 import QtCore


@dataclass(frozen=True)
class CommandBinding:
    name: str
    aliases: tuple[str, ...] = ()


@dataclass(frozen=True)
class ShortcutBinding:
    sequence: str
    widget_ref: str = "window"
    context: QtCore.Qt.ShortcutContext = QtCore.Qt.ShortcutContext.WindowShortcut
    show_in_help: bool = True


@dataclass(frozen=True)
class NativeTrigger:
    label: str


@dataclass(frozen=True)
class KeyRoute:
    kind: Literal["single", "sequence", "widget_specific"]
    sequence: tuple[str, ...]
    scope: Literal["global_non_input", "list_widgets", "widget_exact"]
    widget_refs: tuple[str, ...] = ()
    timeout_ms: int | None = None
    show_in_help: bool = True


@dataclass(frozen=True)
class ActionSpec:
    id: str
    description: str
    handler_name: str
    command: CommandBinding | None = None
    shortcuts: tuple[ShortcutBinding, ...] = ()
    key_routes: tuple[KeyRoute, ...] = ()
    native_triggers: tuple[NativeTrigger, ...] = ()
    show_in_help: bool = True


def build_action_specs() -> tuple[ActionSpec, ...]:
    widget_shortcut = QtCore.Qt.ShortcutContext.WidgetShortcut

    return (
        ActionSpec(
            id="listcommands",
            description="List all commands",
            handler_name="_cmd_list_commands",
            command=CommandBinding("listcommands", aliases=("ls",)),
        ),
        ActionSpec(
            id="quit",
            description="Quit the app",
            handler_name="_cmd_quit",
            command=CommandBinding("quit", aliases=("q",)),
        ),
        ActionSpec(
            id="addfolder",
            description="Add files from a folder",
            handler_name="add_folder_dialog",
            command=CommandBinding("addfolder"),
            shortcuts=(ShortcutBinding("Ctrl+O"),),
        ),
        ActionSpec(
            id="refresh",
            description="Refresh known tags",
            handler_name="force_refresh_known_tags",
            command=CommandBinding("refresh"),
            shortcuts=(ShortcutBinding("F5"),),
        ),
        ActionSpec(
            id="resolve",
            description="Resolve IPTC/XMP mismatch",
            handler_name="resolve_mismatch",
            command=CommandBinding("resolve"),
            shortcuts=(ShortcutBinding("Ctrl+R"),),
        ),
        ActionSpec(
            id="addtag",
            description="Add tag from input",
            handler_name="add_keyword_from_input",
            command=CommandBinding("addtag"),
            shortcuts=(ShortcutBinding("Ctrl+Enter"), ShortcutBinding("Ctrl+Return")),
        ),
        ActionSpec(
            id="removetags",
            description="Remove selected tags",
            handler_name="remove_selected_keywords",
            command=CommandBinding("removetags"),
            shortcuts=(ShortcutBinding("Backspace"), ShortcutBinding("Del")),
        ),
        ActionSpec(
            id="focusfilter",
            description="Focus known-tag filter",
            handler_name="_focus_known_filter_select_all",
            command=CommandBinding("focusfilter"),
            shortcuts=(ShortcutBinding("Ctrl+F"), ShortcutBinding("/")),
        ),
        ActionSpec(
            id="focusadd",
            description="Focus add-keyword input",
            handler_name="_focus_add_edit_select_all",
            command=CommandBinding("focusadd"),
            shortcuts=(ShortcutBinding("Ctrl+L"),),
            key_routes=(KeyRoute(kind="single", sequence=("i",), scope="global_non_input"),),
        ),
        ActionSpec(
            id="focusfiles",
            description="Focus files pane",
            handler_name="_focus_pane_files",
            command=CommandBinding("focusfiles"),
            key_routes=(KeyRoute(kind="single", sequence=("f",), scope="global_non_input"),),
        ),
        ActionSpec(
            id="focustags",
            description="Focus known-tags pane",
            handler_name="_focus_pane_known",
            command=CommandBinding("focustags"),
            key_routes=(KeyRoute(kind="single", sequence=("t",), scope="global_non_input"),),
        ),
        ActionSpec(
            id="togglebackup",
            description="Toggle keep *_original backups",
            handler_name="_toggle_keep_backup",
            command=CommandBinding("togglebackup"),
            shortcuts=(ShortcutBinding("Ctrl+Shift+B"),),
        ),
        ActionSpec(
            id="toggleemptyiptc",
            description="Toggle only IPTC-empty filter",
            handler_name="_toggle_only_iptc_empty",
            command=CommandBinding("toggleemptyiptc"),
            shortcuts=(ShortcutBinding("Ctrl+Shift+E"),),
        ),
        ActionSpec(
            id="panenext",
            description="Focus next pane",
            handler_name="_focus_next_pane",
            command=CommandBinding("panenext"),
            shortcuts=(ShortcutBinding("Ctrl+W, W"), ShortcutBinding("Ctrl+W, Ctrl+W")),
        ),
        ActionSpec(
            id="paneleft",
            description="Focus left pane",
            handler_name="_focus_pane_left",
            command=CommandBinding("paneleft"),
            shortcuts=(
                ShortcutBinding("Ctrl+W, H"),
                ShortcutBinding("h", widget_ref="keywordsList", context=widget_shortcut),
            ),
        ),
        ActionSpec(
            id="paneright",
            description="Focus right pane",
            handler_name="_focus_pane_right",
            command=CommandBinding("paneright"),
            shortcuts=(
                ShortcutBinding("Ctrl+W, L"),
                ShortcutBinding("l", widget_ref="files", context=widget_shortcut),
            ),
        ),
        ActionSpec(
            id="panedown",
            description="Focus lower pane",
            handler_name="_focus_pane_down",
            command=CommandBinding("panedown"),
            shortcuts=(ShortcutBinding("Ctrl+W, J"),),
        ),
        ActionSpec(
            id="paneup",
            description="Focus upper pane",
            handler_name="_focus_pane_up",
            command=CommandBinding("paneup"),
            shortcuts=(ShortcutBinding("Ctrl+W, K"),),
        ),
        ActionSpec(
            id="listdown",
            description="Move selection down",
            handler_name="_action_list_down",
            command=CommandBinding("listdown"),
            key_routes=(KeyRoute(kind="single", sequence=("j",), scope="list_widgets"),),
            native_triggers=(NativeTrigger("Down"),),
        ),
        ActionSpec(
            id="listup",
            description="Move selection up",
            handler_name="_action_list_up",
            command=CommandBinding("listup"),
            key_routes=(KeyRoute(kind="single", sequence=("k",), scope="list_widgets"),),
            native_triggers=(NativeTrigger("Up"),),
        ),
        ActionSpec(
            id="listtop",
            description="Jump to top of list",
            handler_name="_action_list_top",
            command=CommandBinding("listtop"),
            key_routes=(
                KeyRoute(kind="sequence", sequence=("g", "g"), scope="list_widgets", timeout_ms=600),
            ),
            native_triggers=(NativeTrigger("Home"),),
        ),
        ActionSpec(
            id="listbottom",
            description="Jump to bottom of list",
            handler_name="_action_list_bottom",
            command=CommandBinding("listbottom"),
            key_routes=(KeyRoute(kind="single", sequence=("G",), scope="list_widgets"),),
            native_triggers=(NativeTrigger("End"),),
        ),
        ActionSpec(
            id="knownnext",
            description="Next known-tag match",
            handler_name="_action_known_next",
            command=CommandBinding("knownnext"),
            shortcuts=(ShortcutBinding("n"),),
        ),
        ActionSpec(
            id="knownprev",
            description="Previous known-tag match",
            handler_name="_action_known_prev",
            command=CommandBinding("knownprev"),
            shortcuts=(ShortcutBinding("N"),),
        ),
        ActionSpec(
            id="visual",
            description="Toggle visual tag selection",
            handler_name="_toggle_visual_keywords",
            command=CommandBinding("visual"),
            shortcuts=(
                ShortcutBinding("Shift+V", widget_ref="keywordsList", context=widget_shortcut),
            ),
        ),
        ActionSpec(
            id="yank",
            description="Yank selected tags",
            handler_name="_yank_selected_tags",
            command=CommandBinding("yank"),
            shortcuts=(
                ShortcutBinding("Ctrl+C", widget_ref="keywordsList", context=widget_shortcut),
            ),
            key_routes=(
                KeyRoute(
                    kind="sequence",
                    sequence=("Space", "y"),
                    scope="list_widgets",
                    widget_refs=("keywordsList",),
                    timeout_ms=600,
                ),
            ),
        ),
        ActionSpec(
            id="paste",
            description="Paste yanked tags",
            handler_name="_paste_yanked_tags",
            command=CommandBinding("paste"),
            shortcuts=(
                ShortcutBinding("Ctrl+V", widget_ref="files", context=widget_shortcut),
                ShortcutBinding("Ctrl+V", widget_ref="keywordsList", context=widget_shortcut),
            ),
            key_routes=(
                KeyRoute(
                    kind="sequence",
                    sequence=("Space", "p"),
                    scope="list_widgets",
                    widget_refs=("files", "keywordsList"),
                    timeout_ms=600,
                ),
            ),
        ),
        ActionSpec(
            id="escape",
            description="Reset focus / close command line",
            handler_name="_escape_action",
            command=CommandBinding("escape"),
            shortcuts=(ShortcutBinding("Esc"),),
            key_routes=(
                KeyRoute(
                    kind="widget_specific",
                    sequence=("Ctrl+C",),
                    scope="widget_exact",
                    widget_refs=("addEdit", "knownFilter"),
                ),
            ),
        ),
        ActionSpec(
            id="open_command_line",
            description="Open command line",
            handler_name="_open_command_line",
            key_routes=(KeyRoute(kind="single", sequence=(":",), scope="global_non_input"),),
            show_in_help=False,
        ),
        ActionSpec(
            id="complete_command_line",
            description="Complete command line input",
            handler_name="_tab_complete_command_line",
            key_routes=(
                KeyRoute(
                    kind="widget_specific",
                    sequence=("Tab",),
                    scope="widget_exact",
                    widget_refs=("cmdLine",),
                ),
            ),
            show_in_help=False,
        ),
        ActionSpec(
            id="complete_add_edit",
            description="Complete add-tag input",
            handler_name="_tab_complete_add_edit",
            key_routes=(
                KeyRoute(
                    kind="widget_specific",
                    sequence=("Tab",),
                    scope="widget_exact",
                    widget_refs=("addEdit",),
                ),
            ),
            show_in_help=False,
        ),
    )
