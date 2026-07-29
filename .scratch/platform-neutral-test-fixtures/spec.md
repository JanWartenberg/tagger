# Platform-Neutral Coordinator Test Fixtures

Status: completed

## Problem Statement

Coordinator and discovery tests use POSIX-style fixture paths as fake-adapter dictionary keys. On Windows the production coordinator correctly normalizes these paths to Windows absolute paths before calling adapters, so the fakes miss their configured results and report unrelated failures.

## Desired Outcome

The coordinator and affected MainWindow discovery tests express fixture paths through the same normalization contract as production, so their behavior assertions pass unchanged on Windows and Linux.

## Scope

- Normalize fixture roots, discovered paths, fake-adapter result keys, failure keys, and expected event paths through the repository path-normalization contract.
- Preserve production path normalization and Coordinator behavior.
- Cover replacement, additive-drop ordering, index operations, reads, and MainWindow folder/drop discovery with platform-neutral fixtures.

## Out of Scope

Changing user-facing path semantics or weakening Windows absolute-path normalization.
