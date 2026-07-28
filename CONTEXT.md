# TAGGER

TAGGER supports viewing, finding, and editing photo metadata while preserving a focused keyboard-driven workflow.

## Language

**Photo Workspace**:
The current collection of photos being worked on, including its active view mode, filter, selection, and restorable prior view state. It is the source of what the photo-files pane presents.
_Avoid_: File list, photo list, files pane model

**IPTC-empty filter view**:
The photo set produced by a user-triggered IPTC-empty filter run. Tagging photos afterward must not remove them from this filtered list. The set remains stable after metadata mutations; the user explicitly reactivates the filter to compute a new view from current file metadata.

**Capture date**:
The calendar date used by a date query. It comes from `EXIF:DateTimeOriginal`; if that is absent, it comes from `EXIF:CreateDate`. Its stored time or timezone never changes its calendar day. A photo without either value, or with an unusable date value, has no capture date and is date-unknown.

**Confirmed metadata state**:
The latest metadata state that TAGGER has successfully read from or written to a photo file. It is the basis for restoring a failed mutation and recomputing later pending mutations.

**Pending tag mutation**:
A requested metadata change that TAGGER has displayed but that has not yet been confirmed as written to the photo file. It must remain visibly distinct from confirmed metadata while the user continues working. A pending tag mutation is either queued or in flight.

**Queued tag mutation**:
A pending tag mutation that has not yet been sent to ExifTool. TAGGER discards it when its photo leaves the Photo Workspace.

**In-flight tag mutation**:
A pending tag mutation already sent to ExifTool. It may complete after a Photo Workspace change, but it must not update the new Photo Workspace view.

**Failed tag mutation**:
A pending tag mutation that could not be written. TAGGER restores the last confirmed metadata state and exposes a user-initiated retry instead of presenting the failed requested state as file truth. TAGGER does not retry it automatically. It persists for the application session after its photo leaves the Photo Workspace, and is shown again if that photo returns.

**Unresolved mutation indicator**:
A persistent, non-alarming attention marker on a photo with a failed tag mutation. It is distinct from the pending-mutation indicator and tells the user that an explicit retry remains available. It presents the normal retry guidance, not a technical failure reason.

**Application session**:
The lifetime of one running TAGGER process. Failed tag mutations and their unresolved mutation indicators exist only during this session and are not persisted across restart.

**Partial tag mutation**:
A multi-photo tag mutation with both confirmed and failed photo writes. Confirmed photos retain their changes; only failed photos are restored, marked failed, and included in a retry.

**Superseding tag mutation**:
A later requested tag change for the same photo that covers failed intent for one or more tag identities. The later intent wins for each covered tag; only unrelated failed intent remains visible and retryable.

**Tag intent**:
A requested add or remove operation for one tag identity on one photo. Tag intents are compared case-insensitively. A mutation may contain multiple tag intents. When replayed after a fresh read, it takes precedence for its tag identity while unrelated external metadata changes remain intact.

**Pending mutation sequence**:
The ordered pending tag mutations for one photo. If an earlier mutation fails, later pending mutations remain requested and are recomputed from the last confirmed metadata state rather than discarded.
