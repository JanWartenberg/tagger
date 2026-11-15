# Direct Photos First

Recursive folder loading groups photos directly in the chosen folder before all
photos from its subfolders. Each group retains the existing case-insensitive
alphabetical full-path ordering; deeper folders are not independently promoted.
This applies to Add folder and each dropped folder. Multiple drops retain their
initiation order, and explicitly added individual files retain insertion order.

F5 replaces the refreshed photo block at its first prior position, using the
same grouping. Unrelated photos retain their relative order. Surviving selection,
active photo, filter conditions and the top visible photo's pixel offset survive
the refresh, including batched rendering of large collections.

Filename, directory exclusion and stable IPTC-empty filters preserve source order.
Indexed tag/date search remains a temporary database-wide result view with its
existing result order; leaving search restores the grouped folder view.

Verification seams: BackgroundCoordinator discovery events, PhotoWorkspace
snapshots and public Qt interactions. Extend existing disposable-JPEG scroll and
refresh acceptance scenarios; do not use personal photos. The maintainer accepted
the visible result and requested a final review followed by a commit.
