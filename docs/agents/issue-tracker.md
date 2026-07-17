# Issue tracker: Local Markdown

Issues and specs (also known as PRDs) for this repository live as Markdown files in `.scratch/`.

## Conventions

- One feature per directory: `.scratch/<feature-slug>/`
- The spec is `.scratch/<feature-slug>/spec.md`
- Implementation issues are one file per ticket at `.scratch/<feature-slug>/issues/<NN>-<slug>.md`, numbered from `01`
- Never combine all tickets into one file
- Triage state is recorded as a `Status:` line near the top of each issue file
- Comments and conversation history append under a `## Comments` heading

## Publishing

When a skill says to publish to the issue tracker, create the appropriate Markdown file under `.scratch/<feature-slug>/`, creating directories as needed.

When a skill says to fetch a ticket, read the referenced file or issue number from that directory.

## Blocking work

Tickets declare dependencies with a `Blocked by: NN, NN` line. A ticket is unblocked when every listed ticket has a completed status.
