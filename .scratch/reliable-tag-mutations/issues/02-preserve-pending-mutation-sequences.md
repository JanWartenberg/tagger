# 02 — Preserve Pending Mutation Sequences

Status: ready-for-agent
Category: bug
Priority: high
Blocked by: 01

**What to build:**

When a user makes multiple tag changes to the same photo before earlier writes finish, TAGGER must preserve later Pending tag mutations if an earlier one fails. Before writing a pending mutation or retrying one, TAGGER must obtain current file metadata and replay the original user intent, preserving unrelated metadata changes made outside TAGGER.

- [ ] A later requested mutation remains pending after an earlier mutation for the same photo fails.
- [ ] Later pending intent is recomputed from Confirmed metadata rather than discarded or overwritten by rollback.
- [ ] Execution and retry replay the user's logical tag intent against freshly read file metadata.
- [ ] Unrelated externally added metadata survives the replayed user intent.
- [ ] Tests cover an earlier failure followed by a later pending mutation and an external metadata change before execution or retry.
