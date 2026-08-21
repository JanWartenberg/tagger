from dataclasses import dataclass
from typing import Literal

from PyQt6 import QtCore


@dataclass(frozen=True)
class CommandBinding:
    name: str
    aliases: tuple[str, ...] = ()
    accepts_arguments: bool = False


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
    filter_shortcut = QtCore.Qt.ShortcutContext.WidgetWithChildrenShortcut

    return (
        ActionSpec(
            id="listcommands",
            description="List all commands",
            handler_name="_cmd_list_commands",
            command=CommandBinding("listcommands", aliases=("ls", "list", "h", "help")),
            shortcuts=(ShortcutBinding("F1"),),
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
            id="reindex",
            description="Fully refresh the active photo index",
            handler_name="reindex_active_root",
            command=CommandBinding("reindex"),
        ),
        ActionSpec(
            id="refreshiptc",
            description="Apply updated IPTC-empty index results",
            handler_name="refresh_iptc_empty_view",
            command=CommandBinding("refreshiptc"),
        ),
        ActionSpec(
            id="cancel",
            description="Cancel the active full-index refresh",
            handler_name="cancel_active_refresh",
            command=CommandBinding("cancel"),
        ),
        ActionSpec(
            id="errors",
            description="Show operational errors from this session",
            handler_name="show_error_history",
            command=CommandBinding("errors"),
        ),
        ActionSpec(
            id="retry",
            description="Retry failed tag changes for selected photos",
            handler_name="retry_failed_tag_mutations",
            command=CommandBinding("retry"),
        ),
        ActionSpec(
            id="retryall",
            description="Retry all failed tag changes in the Photo Workspace",
            handler_name="retry_all_failed_tag_mutations",
            command=CommandBinding("retryall"),
        ),
        ActionSpec(
            id="resolve",
            description="Resolve IPTC/XMP keywords for the active photo",
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
            key_routes=(
                KeyRoute(
                    kind="sequence",
                    sequence=("d", "d"),
                    scope="list_widgets",
                    widget_refs=("keywordsList",),
                    timeout_ms=600,
                ),
            ),
        ),
        ActionSpec(
            id="focusdbsearch",
            description="Focus Tags filter",
            handler_name="_focus_db_search_select_all",
            shortcuts=(
                ShortcutBinding("Ctrl+T"),
                ShortcutBinding("Alt+T", "filesFilterBox", context=filter_shortcut),
            ),
        ),
        ActionSpec(
            id="focusdatefilter",
            description="Focus Date filter",
            handler_name="_focus_date_filter_select_all",
            command=CommandBinding("focusdatefilter"),
            shortcuts=(
                ShortcutBinding("Ctrl+D"),
                ShortcutBinding("Alt+D", "filesFilterBox", context=filter_shortcut),
            ),
        ),
        ActionSpec(
            id="focusfilenamefilter",
            description="Focus Filename filter",
            handler_name="_focus_filename_filter_select_all",
            command=CommandBinding("focusfilenamefilter"),
            shortcuts=(
                ShortcutBinding("Ctrl+F"),
                ShortcutBinding("Alt+F", "filesFilterBox", context=filter_shortcut),
            ),
        ),
        ActionSpec(
            id="focusexcludedir",
            description="Focus Exclude folder filter",
            handler_name="_focus_excluded_directory_select_all",
            command=CommandBinding("focusexcludedir"),
            shortcuts=(
                ShortcutBinding("Alt+X", "filesFilterBox", context=filter_shortcut),
            ),
        ),
        ActionSpec(
            id="excludedir",
            description="Exclude a folder name from the workspace",
            handler_name="_command_exclude_directory",
            command=CommandBinding("excludedir", accepts_arguments=True),
        ),
        ActionSpec(
            id="clearexcludedir",
            description="Clear one excluded folder name",
            handler_name="_command_clear_excluded_directory",
            command=CommandBinding("clearexcludedir", accepts_arguments=True),
        ),
        ActionSpec(
            id="togglefilenamematchcase",
            description="Toggle Filename match case",
            handler_name="_toggle_filename_case_sensitive",
            shortcuts=(
                ShortcutBinding("Alt+A", "filesFilterBox", context=filter_shortcut),
            ),
        ),
        ActionSpec(
            id="filterfiles",
            description="Filter current workspace filenames",
            handler_name="_command_filter_files",
            command=CommandBinding("filterfiles", accepts_arguments=True),
        ),
        ActionSpec(
            id="clearfilenamefilter",
            description="Clear filename filter",
            handler_name="clear_filename_filter",
            command=CommandBinding("clearfilenamefilter"),
        ),
        ActionSpec(
            id="clearfilters",
            description="Clear all workspace filters",
            handler_name="clear_all_filters",
            command=CommandBinding("clearfilters"),
            shortcuts=(
                ShortcutBinding("Alt+C", "filesFilterBox", context=filter_shortcut),
            ),
        ),
        ActionSpec(
            id="search",
            description="Search indexed photos",
            handler_name="_command_search",
            command=CommandBinding("search", accepts_arguments=True),
            shortcuts=(
                ShortcutBinding("Alt+S", "filesFilterBox", context=filter_shortcut),
            ),
        ),
        ActionSpec(
            id="clearsearch",
            description="Clear photo-tag search",
            handler_name="clear_db_search",
            command=CommandBinding("clearsearch", aliases=("clear", "back")),
            shortcuts=(ShortcutBinding("Ctrl+Shift+X"),),
        ),
        ActionSpec(
            id="focusadd",
            description="Focus add-keyword input",
            handler_name="_focus_add_edit_select_all",
            command=CommandBinding("focusadd"),
            shortcuts=(ShortcutBinding("Ctrl+L"),),
            key_routes=(
                KeyRoute(kind="single", sequence=("i",), scope="global_non_input"),
            ),
        ),
        ActionSpec(
            id="focusfiles",
            description="Focus files pane",
            handler_name="_focus_pane_files",
            command=CommandBinding("focusfiles"),
            shortcuts=(ShortcutBinding("Alt+1"),),
            key_routes=(
                KeyRoute(kind="single", sequence=("f",), scope="global_non_input"),
            ),
        ),
        ActionSpec(
            id="focuskeywords",
            description="Focus current-tags pane",
            handler_name="_focus_pane_keywords",
            command=CommandBinding("focuscurrenttags"),
            shortcuts=(ShortcutBinding("Alt+3"),),
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
            shortcuts=(ShortcutBinding("Ctrl+E"),),
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
                ShortcutBinding(
                    "h", widget_ref="keywordsList", context=widget_shortcut
                ),
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
            id="listdown",
            description="Move selection down",
            handler_name="_action_list_down",
            command=CommandBinding("listdown"),
            key_routes=(
                KeyRoute(kind="single", sequence=("j",), scope="list_widgets"),
            ),
            native_triggers=(NativeTrigger("Down"),),
        ),
        ActionSpec(
            id="listup",
            description="Move selection up",
            handler_name="_action_list_up",
            command=CommandBinding("listup"),
            key_routes=(
                KeyRoute(kind="single", sequence=("k",), scope="list_widgets"),
            ),
            native_triggers=(NativeTrigger("Up"),),
        ),
        ActionSpec(
            id="listtop",
            description="Jump to top of list",
            handler_name="_action_list_top",
            command=CommandBinding("listtop"),
            key_routes=(
                KeyRoute(
                    kind="sequence",
                    sequence=("g", "g"),
                    scope="list_widgets",
                    timeout_ms=600,
                ),
            ),
            native_triggers=(NativeTrigger("Home"),),
        ),
        ActionSpec(
            id="listbottom",
            description="Jump to bottom of list",
            handler_name="_action_list_bottom",
            command=CommandBinding("listbottom"),
            key_routes=(
                KeyRoute(kind="single", sequence=("G",), scope="list_widgets"),
            ),
            native_triggers=(NativeTrigger("End"),),
        ),
        ActionSpec(
            id="visual",
            description="Toggle visual tag selection",
            handler_name="_toggle_visual_keywords",
            command=CommandBinding("visual"),
            shortcuts=(
                ShortcutBinding(
                    "Shift+V", widget_ref="keywordsList", context=widget_shortcut
                ),
            ),
        ),
        ActionSpec(
            id="yank",
            description="Yank selected tags",
            handler_name="_yank_selected_tags",
            command=CommandBinding("yank"),
            shortcuts=(
                ShortcutBinding(
                    "Ctrl+C", widget_ref="keywordsList", context=widget_shortcut
                ),
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
            id="yankcurrent",
            description="Yank all tags from current file",
            handler_name="_yank_current_file_tags",
            command=CommandBinding("yankcurrent"),
            shortcuts=(
                ShortcutBinding("Ctrl+C", widget_ref="files", context=widget_shortcut),
            ),
            key_routes=(
                KeyRoute(
                    kind="sequence",
                    sequence=("Space", "y"),
                    scope="list_widgets",
                    widget_refs=("files",),
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
                ShortcutBinding(
                    "Ctrl+V", widget_ref="keywordsList", context=widget_shortcut
                ),
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
            id="open",
            description="Open active photo",
            handler_name="_open_selected_photos",
            command=CommandBinding("open"),
            key_routes=(
                KeyRoute(
                    kind="sequence",
                    sequence=("Space", "o"),
                    scope="list_widgets",
                    widget_refs=("files",),
                    timeout_ms=1_000,
                ),
            ),
        ),
        ActionSpec(
            id="opengimp",
            description="Open active photo in GIMP",
            handler_name="_open_selected_photos_in_gimp",
            command=CommandBinding("opengimp", aliases=("gimp",)),
            key_routes=(
                KeyRoute(
                    kind="sequence",
                    sequence=("Space", "g"),
                    scope="list_widgets",
                    widget_refs=("files",),
                    timeout_ms=1_000,
                ),
            ),
        ),
        ActionSpec(
            id="copypath",
            description="Copy selected photo paths",
            handler_name="_copy_selected_photo_paths",
            command=CommandBinding("copypath"),
            key_routes=(
                KeyRoute(
                    kind="sequence",
                    sequence=("Space", "c"),
                    scope="list_widgets",
                    widget_refs=("files",),
                    timeout_ms=1_000,
                ),
            ),
        ),
        ActionSpec(
            id="reveal",
            description="Reveal active photo in Explorer",
            handler_name="_reveal_active_photo",
            command=CommandBinding("reveal"),
            key_routes=(
                KeyRoute(
                    kind="sequence",
                    sequence=("Space", "r"),
                    scope="list_widgets",
                    widget_refs=("files",),
                    timeout_ms=1_000,
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
                    widget_refs=("addEdit",),
                ),
            ),
        ),
        ActionSpec(
            id="open_command_line",
            description="Open command line",
            handler_name="_open_command_line",
            key_routes=(
                KeyRoute(kind="single", sequence=(":",), scope="global_non_input"),
            ),
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
