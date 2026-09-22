# 01 — Prepare TAGGER for GitHub Publication

Status: ready-for-agent
Category: maintenance
Priority: high
Milestone: M9 — GitHub publication readiness
Blocked by: None

## Goal

Prepare TAGGER for publication as a small, clear GitHub repository, following
the intentionally simple shape of the
[ticket-cli repository](https://github.com/JanWartenberg/ticket-cli).

## Next Action

Inspect the tracked tree for private or generated material, then add only the
repository files needed for a clean public checkout and documented local
development.

## Scope

- Add the selected open-source license.
- Improve the README's purpose, prerequisites, setup, run, test, and limitation
  sections for a new user.
- Review `.gitignore` and remove or exclude caches, virtual environments,
  generated files, personal paths, and private photo data.
- Define the smallest reliable lint/test command.
- Add GitHub Actions for Ruff and pytest when they run reliably; avoid
  requiring ExifTool, a GUI session, or real photos unless CI fixtures support
  them.
- Add only short contributor or issue guidance that materially helps public
  use.
- Review the final tracked tree for secrets and machine-specific content before
  publication.

## Out of Scope

- UI or domain-feature work.
- Cloud services, telemetry, or remote photo processing.
- Packaging TAGGER as an executable.
- Unrelated refactoring.

## Acceptance Criteria

- [ ] GitHub owner and repository name are recorded.
- [ ] License decision is recorded and the license file is present.
- [ ] A clean checkout can follow the README to install, run, and test TAGGER.
- [ ] The documented quality/test command succeeds in the supported setup.
- [ ] CI, if added, has an explicit supported environment and reliable scope.
- [ ] No local caches, virtual environments, private photo data, secrets, or
      machine-specific paths are tracked.
- [ ] The resulting repository is intentionally small and similar in shape to
      ticket-cli repository.

## Decision Record

- Repository: `https://github.com/JanWartenberg/tagger`
- Git transport: HTTPS, matching the `ticket` repository.

- License: MIT; `LICENSE` is present.
- CI: Ruff and pytest when reliable in GitHub Actions.
- Development: local-first; agents run the documented checks during changes.
- Release: no packaged release; source-checkout usage only.
