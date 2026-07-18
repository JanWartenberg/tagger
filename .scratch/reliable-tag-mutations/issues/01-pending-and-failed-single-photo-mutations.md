# 01 — Pending and Failed Single-Photo Mutations

Status: ready-for-agent
Category: bug
Priority: high
Blocked by: None — can start immediately

**What to build:**

When a user adds or removes tags for one photo, TAGGER must immediately show the requested metadata as a Pending tag mutation without blocking further interaction. The affected photo-files-pane entry and its detail area must distinguish pending metadata from confirmed metadata. A successful write confirms the change; a failed write restores the Confirmed metadata state and leaves a persistent, visible failed state.

- [ ] A single-photo tag add or remove is visibly pending immediately, while the UI remains interactive.
- [ ] Pending and failed states are visible in both the affected photo-files-pane entry and selected-photo detail area.
- [ ] A successful write alone confirms metadata; only confirmed state updates the index and IPTC-empty visibility.
- [ ] A failed write restores the last Confirmed metadata state rather than presenting requested tags as file truth.
- [ ] Pure mutation-coordination tests and offscreen adapter tests cover pending, success, and failure behavior.
