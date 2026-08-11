# Files-Pane Filter UI Redesign

Status: completed
Priority: medium

## Outcome

The Files pane presents one compact, keyboard-accessible filter box: separate Tags, Date, and Filename inputs; an `Aa` filename-case toggle; an Only-without-IPTC-tags condition; and explicit Search and Clear actions. Tags and Date intersect through the existing indexed-search grammar; Filename remains a workspace-local condition.

The pane shows the workspace count and active filter chips with the current match count, instead of repeating inactive folder-state text. The Known tags pane remains present as a provisional layout choice; its longer-term product role is tracked separately.

## Interaction

- `Ctrl+T`, `Ctrl+D`, and `Ctrl+F` focus Tags, Date, and Filename; `Alt+T`, `Alt+D`, and `Alt+F` do the same inside the filter box.
- `Ctrl+E` toggles Only without IPTC tags. Within the filter box, `Alt+A` toggles filename case matching, `Alt+S` applies indexed search, and `Alt+C` clears all conditions.
- `:focusdatefilter`, `:focusfilenamefilter`, `:filterfiles`, `:clearfilenamefilter`, `:clearfilters`, and `:search` retain their documented responsibilities. `:search` remains the grammar-based command interface.

## Constraints

- Keep Photo Workspace responsible for source membership, conditions, selection repair, and restoration.
- Keep indexing and filesystem work off the UI thread.
- Do not add a second search engine, a filename SQLite query, or a modal date picker.

## Validation

- Cover filter control layout, action-catalogue shortcuts, compound Tags-and-Date searches, workspace counts, active-filter presentation, and clear behavior in pure/offscreen tests.
- Preserve existing filename, IPTC-empty, indexed-search, and keyboard-navigation behavior.
