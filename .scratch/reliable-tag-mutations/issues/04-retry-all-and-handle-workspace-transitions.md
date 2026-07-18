# 04 — Retry All and Handle Workspace Transitions

Status: ready-for-agent
Category: bug
Priority: high
Blocked by: 03

**What to build:**

TAGGER must provide `:retryall` for all failed tag mutations in the current Photo Workspace and must handle Photo Workspace replacement safely. Queued mutations for photos that leave the workspace are discarded. In-flight writes may finish for file and index correctness, but their completion must never alter the replacement workspace view.

- [ ] `:retryall` retries all and only failed mutations belonging to the current Photo Workspace.
- [ ] `:retryall` does not resubmit Pending tag mutations or failures outside the current Photo Workspace.
- [ ] Replacing the Photo Workspace discards queued mutations for departed photos.
- [ ] In-flight completion after replacement does not render or select anything in the replacement workspace, while confirmed file/index state remains correct.
- [ ] Tests cover `:retryall` scope and both queued and in-flight mutation behavior across a Photo Workspace replacement.
