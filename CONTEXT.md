# TAGGER

TAGGER supports viewing, finding, and editing photo metadata while preserving a focused keyboard-driven workflow.

## Language

**Photo Workspace**:
The current collection of photos being worked on, including its active photo, base view mode, active filter conditions, selection, and restorable prior view state. It is the source of what the photo-files pane presents.
_Avoid_: File list, photo list, files pane model

**Active photo**:
The selected Photo Workspace photo that drives the detail pane, preview, and active-only file actions. It may differ from the first photo in display-ordered multi-selection.

**Photo Workspace filter condition**:
A user-visible predicate that narrows the current Photo Workspace. Active conditions combine with logical AND. The current filename and IPTC-empty conditions are independent; future composition may add conditions, but OR/NOT semantics are not yet defined.

**Files-pane filter block**:
The group of input controls used to create and clear Photo Workspace filter conditions. Its visibility is presentation state and is distinct from the active conditions, which remain visible and individually removable when the block is collapsed.
_Avoid_: Filter pane, filter state

**Filename filter**:
A live, workspace-local Photo Workspace filter condition based only on a photo's normalized basename, including its extension. It never searches directories, full paths, or photos outside the current Photo Workspace. It applies after the complete current indexed-search or IPTC-empty source is determined and remains active when those conditions change.

**Directory exclusion**:
A workspace-local Photo Workspace filter condition that excludes paths below one or more exact normalized ancestor-directory names. Names are NFC-normalized, case-insensitive, insertion-ordered, and compose as AND/NOT conditions with all other filters. It never accepts paths, filename text, or partial names.

**IPTC-empty filter view**:
The photo set produced by a user-triggered IPTC-empty filter run. Tagging photos afterward must not remove them from this filtered list. The set remains stable after metadata mutations; the user explicitly reactivates the filter to compute a new view from current file metadata.

**Canonical tag field**:
`IPTC:Keywords` is TAGGER's authoritative tag field. `XMP-dc:Subject` is a compatibility mirror, not an alternative source of TAGGER tag truth.

**Capture date**:
The calendar date used by a date query. It comes from `EXIF:DateTimeOriginal`; if that is absent, it comes from `EXIF:CreateDate`. Its stored time or timezone never changes its calendar day. A photo without either value, or with an unusable date value, has no capture date and is date-unknown.

### Index

**Index root**:
The top-level photo folder whose descendant photos TAGGER tracks in one index. The index is a SQLite cache stored inside that folder in `.tagger/index.sqlite`.

**Indexed search**:
A tag or date search against the SQLite cache for the current index root rather than a live scan of every photo file. An indexed search is active while its result view is still current: it has not been cleared, replaced by another query, or superseded by a Photo Workspace change.

**Stale result**:
An indexed search result whose cached image-file path no longer exists when TAGGER tries to read metadata from that image file.

**Stale-result index repair**:
A background scan of an index root started after TAGGER encounters a stale result. It reconciles the SQLite cache with photo files currently found below that root: removing records for missing files and indexing independently discovered files with their current metadata. It does not identify filesystem renames and is distinct from the IPTC-empty filter's explicit post-index-update refresh workflow.

### Duplicate review

**Duplicate-candidate detector**:
A named, read-only method that examines an immutable set of photo paths and reports groups worth human assessment together with the evidence used. A detector does not assert that its candidates are duplicates and does not choose or mutate tags.

**Duplicate candidate group**:
Two or more photos associated by one Duplicate-candidate detector. The group remains a candidate until a person assesses its members; a photo series sharing a timestamp is therefore one valid candidate group rather than a confirmed duplicate set.
_Avoid_: Duplicate group, confirmed duplicates

**Duplicate scan scope**:
The immutable photo-path set supplied to one duplicate scan. Its origin, such as the current index database or a selected subfolder, is independent from the chosen Duplicate-candidate detector.

**Same-capture-timestamp detector**:
The default Duplicate-candidate detector. It groups equal effective capture timestamps, preferring `EXIF:DateTimeOriginal` and using a labelled `EXIF:CreateDate` fallback. Equality is evidence for assessment, not proof of image identity.

**Tag propagation plan**:
An explicitly reviewed choice of one source photo, selected target photos, and tag additions within a Duplicate candidate group. It does not change metadata until the user confirms it through the normal Tag mutation workflow.

### Tag mutations

**Tag mutation**:
A change to one or more tags in a photo file. TAGGER treats it as a change to the canonical `IPTC:Keywords` field; `XMP-dc:Subject` is its compatibility mirror.

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

**Session error**:
A timestamped, user-reviewable record of an operational failure during one Application session. It includes one aggregate record for a failed tag mutation, but excludes expected input validation and workflow-state guidance. It is not persisted across restart.

**Partial tag mutation**:
A multi-photo tag mutation with both confirmed and failed photo writes. Confirmed photos retain their changes; only failed photos are restored, marked failed, and included in a retry.

**Superseding tag mutation**:
A later requested tag change for the same photo that covers failed intent for one or more tag identities. The later intent wins for each covered tag; only unrelated failed intent remains visible and retryable.

**Tag intent**:
A requested add or remove operation for one tag identity on one photo. Tag intents are compared case-insensitively. A mutation may contain multiple tag intents. When replayed after a fresh read, it takes precedence for its tag identity while unrelated external metadata changes (edits made outside TAGGER) remain intact.

**Pending mutation sequence**:
The ordered pending tag mutations for one photo. If an earlier mutation fails, later pending mutations remain requested and are recomputed from the last confirmed metadata state rather than discarded.
