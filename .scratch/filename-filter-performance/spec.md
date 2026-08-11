# Responsive Filename Filtering and Performance Baseline

Status: needs-triage
Priority: high

## Problem Statement

Typing into **Filter filenames** can freeze TAGGER for roughly 30 seconds. The field currently applies the workspace-local condition on every keystroke, so the UI must remain responsive while a user enters a query even for a large Photo Workspace.

## Desired Outcome

Filename filtering acknowledges typing immediately but waits 700 ms after the last edit before applying the condition. The eventual result is computed only from the already active Photo Workspace filter sources, never by broadening to an index-wide, filesystem, or metadata search. TAGGER also gains an evidence-based performance baseline and investigation plan for other interactive slowdowns.

## Required Investigation

- Build and run a deterministic, agent-runnable timing harness for a large workspace that can demonstrate the filename-input freeze before a fix and enforce a response budget afterward. Measure debounce delay, `PhotoWorkspace` filtering/snapshot work, Qt list rendering, and event-loop blocking separately.
- Profile the current call chain before choosing an execution model. Determine whether debounce and incremental/coalesced rendering are sufficient or whether the derived filter computation needs a non-blocking worker.
- If a worker is justified, preserve latest-input-wins semantics: stale results must not alter visible membership, selection, active photo, scroll restoration, or status feedback. Keep Photo Workspace as the owner of logical state.
- Establish a small repeatable baseline for other known interactive paths—large workspace rendering, indexed search result rendering, IPTC-empty filtering, metadata loading, and preview loading—and create separately scoped follow-up tickets only for measured regressions.

## Constraints

- The 700 ms debounce applies only to live filename-condition application. Typing itself, focus, Escape, clear, and current active-filter state must remain immediately responsive.
- Apply the filename predicate only after the complete current natural source is available: folder membership intersected with active indexed-search and IPTC-empty conditions. Do not schedule SQLite, filesystem, ExifTool, or image-decoding work merely because a filename query changed.
- Preserve literal, NFC-normalized basename matching and the existing case-sensitivity behavior. Do not turn the feature into directory/full-path search, globbing, regex, or a general query language.
- Preserve condition composition, individual clear and clear-all semantics, empty-state feedback, selection repair, restoration, command/shortcut behavior, and stale-completion safeguards.
- Do not assume a larger thread pool fixes UI latency; choose any asynchronous seam only after profiling.
