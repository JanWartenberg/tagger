# SQLite Connection Lifecycle

Status: completed

## Problem Statement

`PhotoIndex` uses `with self._connect() as conn`, but the SQLite connection context manager commits or rolls back without closing the connection. Open connections produce `ResourceWarning`s and prevent Windows from deleting temporary `index.sqlite` files after tests.

## Desired Outcome

Every `PhotoIndex` operation closes its SQLite connection deterministically on success and failure while preserving transaction, migration, WAL, and query behavior.

## Scope

- Introduce one internal connection-lifecycle seam that commits or rolls back as appropriate and always closes.
- Migrate every `PhotoIndex` caller currently using `_connect()` as a context manager.
- Preserve nested write transaction behavior and schema migration semantics.

## Out of Scope

Schema redesign, changing SQLite pragmas, or changing query results.
