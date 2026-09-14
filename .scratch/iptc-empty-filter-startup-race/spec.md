# IPTC-Empty Filter Startup Race

Status: needs-triage

Opening a large folder and immediately pressing `Ctrl+E` can show zero IPTC-empty matches while the folder's SQLite index is still being populated. The filter must not leave a provisional startup result incorrectly empty; after indexing completes, existing untagged photos must be included without requiring the user to toggle the filter again.

See [issue 01](issues/01-prevent-empty-startup-iptc-filter-result.md) for the reproduction, investigation scope, and acceptance criteria.
