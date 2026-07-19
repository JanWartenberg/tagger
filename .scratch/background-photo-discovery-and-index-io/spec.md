# Background Photo Discovery and Index I/O

Status: ready-for-agent
Priority: high

## Problem Statement

Opening a large folder or dropping a directory can traverse the filesystem on the Qt UI thread. Several index operations also create SQLite connections, inspect the filesystem, or read and write SQLite directly from UI callbacks. This makes TAGGER unresponsive for large collections and permits overlapping index writers for the same database.

## Desired Outcome

The Photo Workspace remains responsive while folders are discovered and while the SQLite index is read or maintained. A Qt-free Coordinator module owns the asynchronous discovery and index-I/O rules behind a small, testable interface. `MainWindow` remains a Qt adapter: it forwards user intent, marshals completed immutable events to the UI thread, forwards facts to `PhotoWorkspace`, and renders the resulting snapshot.

The normal folder-tagging workflow remains the default. This work is a behavior-preserving responsiveness and locality improvement, except for the explicitly specified loading and non-modal-error feedback below.

## Goals

1. Folder-dialog discovery and dropped-directory discovery never traverse the filesystem on the Qt UI thread.
2. SQLite reads and writes that can scale with photo count never run in UI callbacks.
3. A completed current folder discovery makes its photos usable before indexing finishes.
4. Superseded work can never alter the active workspace, visible loading state, selection, active root, search results, or known-tags list.
5. SQLite writes to one index root never overlap.
6. The complex scheduling, ordering, stale-result, and index-write behavior has locality in a Qt-free deep module and can be tested without widgets, real filesystem traversal, SQLite, or ExifTool.

## Non-Goals

- Change the SQLite schema, search syntax, metadata format, or `PhotoWorkspace` behavior.
- Complete deferred reverse-search work from `INDEXING_PLAN.md`.
- Cancel an already running filesystem traversal, SQLite operation, or ExifTool process.
- Implement a live discovery count. This is a separate low-priority backlog item.
- Implement error history or `:errors`. This is a separate low-priority backlog item.
- Remove or redesign the known-tags pane. That product decision is a separate low-priority backlog item.
- Extract input routing, preview loading, or tag-mutation coordination from `MainWindow`. The Coordinator is only the first, narrow extraction tracked by the Main Window Coordinator Decomposition spec.

## Verified Current-State Findings

These are source-analysis facts, not remaining triage decisions.

- `MainWindow.add_folder_dialog` traverses a selected folder with `Path.rglob()` on the UI thread.
- `extract_image_paths_from_urls` traverses a dropped directory with `Path.rglob()` before it emits `filesDropped`; both the file-list and window drop paths therefore block today.
- A first `PhotoIndex.sync_root()` is already dispatched through `Worker`, but it traverses the directory a second time after folder discovery.
- `PhotoIndex.is_initialized()`, `has_photos()`, `update_states()`, `search_photos()`, and `load_tags_for_root()` are currently reachable from UI callbacks. Connection creation also ensures schema and configures SQLite pragmas.
- The generic `Worker` and global `QThreadPool` already run full-root sync, single-photo metadata reads, preview loading, IPTC filtering, and tag mutations. The current worker provides no cancellation, priority, or work-type scheduling policy.
- Full sync, missing-path indexing, selected-photo index updates, and confirmed tag-mutation index updates can currently write one index database concurrently. WAL is enabled, but there is no write coordinator or configured busy timeout.
- Current stale protection is uneven: index sync checks only an active root, missing-path indexing has no completion guard, and search is synchronous.
- Rendering a completed large path collection still creates Qt list items on the UI thread. This remains a Qt-adapter responsibility; it must not move into `PhotoWorkspace` or the Coordinator.

## Architecture

### Coordinator module and seam

Introduce one separate Qt-free **Coordinator module** for background discovery and index I/O. The module is the seam between:

- the Qt adapter, which expresses user intent and renders results;
- injected discovery and index **adapters**, which perform external filesystem, SQLite, and metadata work; and
- an injected background-runner **adapter**, which executes work.

The Coordinator is a deep module. Its interface hides request identity, stale-result rejection, additive-drop ordering, root ownership, scheduling, serial write queues, and incremental-write coalescing. Callers must not reproduce these rules.

The Coordinator must not import PyQt, create widgets, mutate `PhotoWorkspace`, call `MainWindow` methods, or retain widget/cache state. It publishes immutable completion events to an injected event sink. In production, the Qt adapter is responsible for marshaling that event into the UI thread (for example through one Qt signal). Tests may use a collecting event sink.

### Dependencies

The Coordinator accepts dependencies rather than constructing concrete implementations:

- a discovery adapter for folder and dropped-directory traversal;
- an index adapter/factory for initialization checks, sync, reads, and writes;
- a background-runner adapter;
- an event sink for immutable completion events.

Production wraps the existing `QThreadPool` in the runner adapter. Tests use a deterministic runner that exposes scheduled work and controls completion order. Do not add a second application thread pool.

### Coordinator interface requirements

The exact Python names and dataclass names are implementation details, but the interface must support these intents and results without exposing queue internals:

| Intent from Qt adapter | Required Coordinator behavior | Immutable completion fact |
| --- | --- | --- |
| Replace workspace from a folder-dialog selection | Start a replacement discovery with a new workspace/request identity. | Discovery succeeded with ordered normalized paths, returned no paths, or failed. |
| Add a dropped directory | Start additive discovery for the current workspace and assign its drop sequence. | The same discovery facts, released in drop initiation order. |
| Ensure/sync an index from discovered paths | Check initialization and enqueue a full sync as required, without a second traversal. | Index progress/completion or failure with root and request identity. |
| Submit confirmed metadata states | Resolve the path's root, coalesce pending incremental states by normalized path, and enqueue a write. | Successful commit or failure. |
| Search the index | Run an identified read in the background. | Current query, root, and matching paths or failure. |
| Refresh known tags | Run an identified read in the background. | Current root/request and tag snapshot or failure. |

Every event contains sufficient immutable identity to decide whether it still belongs to the current workspace, root, request, search, known-tag refresh, and/or additive-drop sequence. The Coordinator performs its own scheduling and stale rules; the Qt adapter performs the final UI-context check before rendering and must never render an event whose identity is no longer current.

## User-Visible Discovery Contract

### Folder-dialog reload

1. Selecting a folder through **Add folder** is a replacement operation, preserving the current reload meaning.
2. The Qt adapter immediately clears the prior Photo Workspace and presents a loading state while discovery runs.
3. The files pane shows a vertically centered, clearly non-row message such as `Loading photos…`. It must not look like one photo-path list item.
4. The first implementation uses an indeterminate message only. It has no running found-path count.
5. Discovery collects the complete ordered, normalized path result off-thread. It does not add batches progressively to the files pane.
6. A current successful non-empty result is applied atomically through the normal `PhotoWorkspace` reload/add intents, then rendered. Existing selection rules remain the workspace's responsibility.
7. The completed current paths are rendered before initial index work completes. The files are immediately selectable, scrollable, previewable, and taggable.
8. A current successful empty result leaves the replacement workspace empty and uses the normal non-error empty-pane presentation.
9. A current failed result leaves the replacement workspace empty, replaces loading with a vertically centered non-row `No photos loaded` state, and reports the failure in the footer. The old workspace is not restored.

### Dropped directory

1. Dropping a directory preserves the existing additive behavior: it discovers the directory in the background and adds completed paths to the current Photo Workspace. It does not replace that workspace.
2. The existing files pane remains interactive and scrollable while discovery runs. Do not cover it with the replacement-loading pane.
3. The footer shows `Loading photos…` while the additive discovery is pending.
4. A completed current result appends its paths without disrupting existing selection or scroll anchoring.
5. If multiple directories are dropped before their discoveries complete, their results are appended in **drop initiation order**, not completion order. A later small directory that completes first waits behind earlier pending drops.
6. If the workspace is replaced before an additive discovery completes, that old completion is stale and is discarded. It must not append to the replacement workspace.

### Staleness and cancellation

- Do not actively cancel discovery, ExifTool, filesystem, or SQLite operations.
- Starting a folder-dialog replacement creates a new workspace/request identity. Older replacement discovery work may finish but is discarded.
- Additive dropped-directory results remain eligible only for the workspace generation in which they were started, and are released according to their drop sequence.
- A stale completion must not change files-pane contents, selection, scroll state, loading presentation, active index root, known tags, search view, or footer success/error feedback.

## Indexing Contract

### Initial indexing after discovery

- After a current discovery result is rendered, initial indexing starts independently in background work. SQLite initialization checks, membership checks, metadata reads, and index writes must not delay files-pane availability.
- The footer shows `Indexing photos…` while initial indexing is pending. On success it shows the existing concise `Index ready: …` summary.
- Initial sync receives and reuses the completed discovery path set rather than traversing the directory a second time.
- Reusing that path set must retain the current sync semantics: compare mtime and size, read metadata for new or changed photos, update rows/tags, and delete rows absent from the discovered current set.
- A confirmed tag mutation for a departed photo still submits index maintenance for that photo's resolved root. Its completion updates index correctness but must not render into a replacement workspace.

### Per-root write queue

- Exactly one serial background write queue exists per resolved index root.
- Full sync, missing-path indexing, selected-photo updates, and confirmed tag-mutation updates targeting that root run through that queue. UI callbacks only submit work; they never call SQLite writes directly.
- Pending incremental updates are coalesced by normalized photo path before they execute. The newest confirmed state for a path wins.
- Full sync remains a distinct queue operation. It is not cancelled or preempted by a confirmed tag update. A confirmed update submitted while a full sync runs executes afterward, preventing a later full-sync completion from overwriting that newer update.
- A failed queue operation is reported but does not stop the queue. Later queued operations continue.

### Index reads

- Database search, known-tag loading, initialization checks, and membership checks run off the UI thread.
- Reads may run in parallel with the serial per-root write queue and observe the last committed, internally consistent state. They do not wait behind a long full sync.
- Search and known-tag completions carry root and request identity. Only the newest still-current result is eligible to update UI state.

## Search and Known-Tags Contract

### Database search

- Starting a search shows `Searching index…` in the footer.
- The files-pane view remains visible and usable while the read runs; do not clear or flicker it.
- Only the current query/root/workspace result is applied, atomically, through the existing Photo Workspace database-search intent.
- A stale, failed, or superseded search never overwrites a newer search or a workspace replacement.

### Known tags and autocomplete

- A known-tags refresh retains the existing list until a current completion atomically replaces it. Do not add noisy footer feedback for routine refreshes.
- Automatically triggered known-tag refreshes after index changes begin only after the corresponding write operation commits successfully.
- Pressing Tab for tag autocomplete remains purely in-memory: it reads the currently displayed known-tags snapshot and never initiates or waits for SQLite I/O.
- `Filter known tags…` filters the loaded snapshot locally and immediately. It must not request SQLite on every keystroke.
- Submit a known-tags read only after relevant committed data changes, workspace/root changes, or explicit user refresh.

## Feedback and Errors

- Discovery and index errors are non-modal. They appear in the footer/status bar and never interrupt work with a modal dialog.
- A discovery or index error does not make already rendered photos unusable.
- The current scope has no durable/session error history UI. A timestamped `:errors` command is recorded separately in the backlog.
- Routine background refreshes do not overwrite more relevant current footer feedback with stale success/error messages.

## Ownership Rules

| Concern | Owner |
| --- | --- |
| Membership, ordering, visibility, selection repair, active photo, filter/search logical view | `PhotoWorkspace` |
| Widget creation, pane loading/empty presentation, focus, scroll preservation, Qt signal delivery, final UI rendering | `MainWindow` / Qt adapter |
| Filesystem discovery, index-I/O orchestration, identities, stale rules, additive result ordering, write serialization and coalescing | Coordinator module |
| Concrete traversal, SQLite access, ExifTool-backed metadata reads used by sync | Injected adapters |
| Background execution mechanics | Injected runner adapter; production adapter wraps existing `QThreadPool` |

## Testing Requirements

### Pure Coordinator tests

Use a deterministic runner, collecting event sink, fake discovery adapter, and fake index adapter. Do not import PyQt, invoke ExifTool, use real SQLite, traverse real folders, or use sleeps.

Cover at least:

1. Folder-dialog discovery immediately has a replacement identity; a successful result is emitted once with ordered normalized paths.
2. A replacement started after another replacement discards the older completion, including an older failure.
3. Additive directory discoveries remain usable only for their original workspace generation.
4. Multiple additive discoveries completing out of order are released in drop initiation order.
5. Initial sync receives exactly the completed discovery path set and does not ask the discovery adapter to traverse again.
6. Per-root writes never overlap, while writes for different roots may be independently scheduled if the runner permits it.
7. Repeated pending updates for one path coalesce to the newest confirmed state.
8. A confirmed update submitted during full sync runs after that sync.
9. A failed write leaves later queue work runnable.
10. Reads are scheduled off-thread, may run with a write in progress, and observe a committed index snapshot.
11. Superseded search and known-tag requests do not produce UI-eligible events.

### Qt adapter tests

Run offscreen with controlled completions. Assert observable behavior rather than thread timing or Coordinator private fields.

Cover at least:

1. Folder-dialog reload immediately clears the previous workspace and displays the vertically centered non-row loading state.
2. Current completed folder discovery renders paths atomically before index completion; those paths can be selected and tagged while indexing continues.
3. Current folder-discovery failure leaves the replacement workspace empty with its non-row empty state and reports only in the footer.
4. A stale folder result or failure cannot change a replacement workspace.
5. A dropped-directory discovery leaves current paths selectable and scrollable, uses footer feedback, and appends its result without losing selection or scroll anchoring.
6. Two drops that complete out of order appear in initiation order.
7. Search retains the old view until the current result applies atomically; stale search results are ignored.
8. Known tags retain the old list until current completion; text filtering is local and Tab causes no database request.
9. Discovery/index failures do not invoke a modal error dialog.
10. Index completion and stale results do not overwrite current workspace feedback or known-tag state.

### Validation

- Run Ruff on all modified Python files and tests without reformatting unrelated legacy code.
- Run the full unit suite: `python3 -m unittest discover -s tests -v`.
- Run the Windows offscreen acceptance command from the activated environment:
  `set QT_QPA_PLATFORM=offscreen && python -m unittest discover -s tests -v`.
- Run `git diff --check`.

## Suggested Implementation Slices for Ticketing

The slices are ordered to retain behavior and keep interfaces reviewable. Do not implement the entire rewrite as one ticket.

1. **Coordinator interface and deterministic tests**
   - Define immutable intents/events and injected discovery/index/runner adapters.
   - Implement identities, stale-result rejection, additive-drop ordering, event sink delivery, and pure tests.
   - No MainWindow migration beyond a minimal integration seam.

2. **Background discovery and files-pane states**
   - Move folder-dialog and dropped-directory traversal behind the Coordinator.
   - Implement replacement loading/empty states, additive footer feedback, atomic completion application, selection/scroll preservation, and stale rejection.
   - Keep index behavior temporarily delegated through the Coordinator seam.

3. **Serial index writes and discovery-path sync**
   - Change index sync to consume discovered paths without a second traversal.
   - Move initialization/membership checks and all writes into the per-root queue.
   - Implement coalescing, full-sync ordering, failure-continuation behavior, and commit-triggered refreshes.

4. **Background reads, search, and known tags**
   - Move search and known-tag reads behind identified Coordinator requests.
   - Preserve old views/lists until atomic current completion.
   - Make known-tag filtering local and preserve in-memory Tab autocomplete.

5. **Adapter characterization, cleanup, and acceptance**
   - Remove superseded UI-thread index/discovery paths.
   - Add offscreen coverage for all current/stale/error/order cases and complete validation.

## Handoff Notes

All product and architectural decisions necessary for ticketing are resolved. Remaining choices are implementation details constrained by this specification: Python names for dataclasses and methods, the exact adapter protocols, token representation, SQLite retry/timeout mechanics, and test-helper shape. They must preserve the contracts above and do not require renewed product triage.
