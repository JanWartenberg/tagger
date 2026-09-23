# TAGGER GitHub Publication Readiness

Status: completed
Priority: high

## Goal

Prepare TAGGER as a small, understandable public GitHub repository, using the
simple repository shape of the
[ticket-cli repository](https://github.com/JanWartenberg/ticket-cli) as the
reference.

## Product Direction

TAGGER remains a local Python/PyQt application. The GitHub repository should
make it easy for a new user to understand what it does, install its
prerequisites, run it, test it, and understand the project license and current
limitations.

## Required Preparation

- Choose and record the GitHub repository name and owner.
- Add a suitable open-source `LICENSE`.
- Make the README complete for a fresh checkout: purpose, screenshots or
  example usage if available, Windows prerequisites, ExifTool setup, Python
  environment, run command, tests, and known limitations.
- Add the minimum project metadata needed for a Python project, without
  introducing a packaging framework unless it is necessary for installation.
- Add a small, reproducible test/quality command and document it.
- Add GitHub Actions for Ruff and pytest when they run reliably in CI; do not
  make ExifTool or a Windows desktop session an accidental CI requirement.
- Review `.gitignore` and repository contents for local caches, virtual
  environments, generated files, personal paths, and other material that must
  not be published.
- Add contributor and issue guidance only if it remains short and useful.
- Verify that the published tree contains no secrets, private photo data, or
  machine-specific configuration.

## Out of Scope

- Rewriting TAGGER's UI or architecture.
- Adding cloud storage, telemetry, accounts, or remote photo processing.
- Requiring users to package TAGGER as a distributable executable.
- Broad refactoring unrelated to publication readiness.

## Acceptance Criteria

- [x] Repository owner and public repository name are recorded.
- [x] License decision is recorded and the selected license file is present.
- [x] A clean checkout has a complete, accurate quick-start path.
- [x] A documented test/quality command succeeds in the supported local setup.
- [x] CI scope is explicit and does not depend on unavailable desktop/photo
      infrastructure.
- [x] Generated, local, private, and machine-specific files are excluded.
- [x] A publication review confirms that no private photo data or secrets are
      tracked.
- [x] The final repository shape is intentionally small and comparable to the
      ticket-cli repository.

## Decision Record

- Repository: `https://github.com/JanWartenberg/tagger`
- Git transport: HTTPS, matching the `ticket` repository.
- License: MIT; `LICENSE` is present.
- CI: run Ruff and pytest when they work reliably in GitHub Actions.
- Development: local-first; agents run the documented checks during changes.
- Release: no packaged release; document source-checkout usage only.
