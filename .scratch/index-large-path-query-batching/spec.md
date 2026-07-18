# Large Path-Set Index Queries

Status: ready-for-agent
Priority: medium

## Problem Statement

Index operations construct one SQLite `IN` query from every supplied photo path. Large folder loads can exceed SQLite bind-variable limits on some supported environments and create unnecessarily large statements.

## Solution

Make path-set index queries work for arbitrary Photo Workspace sizes by batching database requests behind the existing index interface while preserving results and ordering semantics.

## User Stories

1. As a TAGGER user, I want opening or adding a large photo collection to work reliably.
2. As a TAGGER user, I want index initialization and incremental indexing to preserve their current results.
3. As a maintainer, I want SQLite implementation limits hidden inside the index module.
4. As a maintainer, I want callers to pass a path collection without knowing database parameter limits.

## Implementation Decisions

- Keep batching internal to the index module.
- Use a conservative, documented batch limit below SQLite bind-variable limits.
- Merge batch results into the same set/dictionary contract exposed today.
- Apply the policy consistently to all path-set queries used for membership and sync.

## Testing Decisions

- Use a temporary SQLite database and a path collection larger than the chosen batch limit.
- Assert that membership and sync lookup results equal a small-input baseline.
- Avoid asserting query count except where it is part of the implementation contract.

## Out of Scope

- Schema redesign, global index scheduling, or search syntax changes.

## Further Notes

This is suitable for direct ticketing; it is an internal reliability change with a contained seam.