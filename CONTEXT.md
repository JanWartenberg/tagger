# TAGGER

TAGGER supports viewing, finding, and editing photo metadata while preserving a focused keyboard-driven workflow.

## Language

**Photo Workspace**:
The current collection of photos being worked on, including its active view mode, filter, selection, and restorable prior view state. It is the source of what the photo-files pane presents.
_Avoid_: File list, photo list, files pane model

**Confirmed metadata state**:
The latest metadata state that TAGGER has successfully read from or written to a photo file. It is the basis for restoring a failed mutation and recomputing later pending mutations.

**Pending tag mutation**:
A requested metadata change that TAGGER has displayed but that has not yet been confirmed as written to the photo file. It must remain visibly distinct from confirmed metadata while the user continues working. A pending tag mutation is either queued or in flight.

**Queued tag mutation**:
A pending tag mutation that has not yet been sent to ExifTool. TAGGER discards it when its photo leaves the Photo Workspace.

**In-flight tag mutation**:
A pending tag mutation already sent to ExifTool. It may complete after a Photo Workspace change, but it must not update the new Photo Workspace view.

**Failed tag mutation**:
A pending tag mutation that could not be written. TAGGER restores the last confirmed metadata state and exposes a retry instead of presenting the failed requested state as file truth.

**Partial tag mutation**:
A multi-photo tag mutation with both confirmed and failed photo writes. Confirmed photos retain their changes; only failed photos are restored, marked failed, and included in a retry.

**Pending mutation sequence**:
The ordered pending tag mutations for one photo. If an earlier mutation fails, later pending mutations remain requested and are recomputed from the last confirmed metadata state rather than discarded.
