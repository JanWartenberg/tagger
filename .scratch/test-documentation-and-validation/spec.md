# Test Documentation and Validation Alignment

Status: ready-for-agent
Priority: low

## Problem Statement

The checked-in test documentation no longer matches the available validation environment and recent successful Qt-offscreen runs. This creates uncertainty about which command contributors should run and what coverage it provides.

## Solution

Document the supported validation commands, dependency expectations, and platform-specific acceptance accurately, while keeping the distinction between pure workspace tests and Qt adapter tests clear.

## User Stories

1. As a contributor, I want one accurate command for the Linux test suite.
2. As a Windows maintainer, I want the required offscreen acceptance command documented clearly.
3. As a maintainer, I want to know which tests are pure and which require PyQt6.
4. As a reviewer, I want validation notes to distinguish completed local runs from outstanding Windows acceptance.

## Implementation Decisions

- Keep pure Photo Workspace tests independent of Qt and external tools.
- Keep Qt adapter tests offscreen and dependent on a PyQt6-capable environment.
- Document dependency-version expectations without claiming every agent container has the production environment.
- Keep project documentation in English.

## Testing Decisions

- Run the documented command in the available environment after updating it.
- Verify that the documented command discovers both pure and Qt tests when PyQt6 is available.
- Treat Windows offscreen execution as a separately recorded acceptance step.

## Out of Scope

- Adding a new test framework, continuous-integration provider, or changing production dependencies.

## Further Notes

This is suitable for direct ticketing and should remain a documentation-only change.