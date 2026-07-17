# Domain Docs

This is a single-context repository.

## Before exploring

- Read `CONTEXT.md` at the repository root when it exists.
- Read relevant decisions under `docs/adr/` when that directory exists.
- If either is absent, proceed silently; create domain documentation lazily only when terminology or a durable decision is resolved.

## Vocabulary

Use canonical terms from `CONTEXT.md` in specifications, issues, tests, and architecture discussions. Avoid synonyms explicitly rejected by the glossary.

If a required concept is missing, reconsider whether new terminology is necessary or use the domain-modeling process to define it.

## Decisions

Surface conflicts with existing ADRs explicitly rather than silently overriding them.
