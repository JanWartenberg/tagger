# Unload workspace

Return to an empty Photo Workspace without restarting TAGGER. Approved command:
`:unload`. Place a compact ⏏ button directly after Add folder in both views,
with tooltip `Unload workspace (:unload)` and an accessible name.
Both neighboring buttons use the larger of their natural heights in each view.

Clear loaded photos, selection, details/preview, filters, draft tag input and
temporary duplicate results/scope. Cancel obsolete loading and ignore late
results. Keep the active application view, saved metadata, index databases,
preferences, remembered ignores and session diagnosis/retry history. Block
unloading while tag writes are running or queued, without discarding writes.
Allow repeated unloading and subsequent loading/searching.
