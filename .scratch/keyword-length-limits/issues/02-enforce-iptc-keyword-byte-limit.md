# 02 — Enforce the IPTC Keyword Byte Limit

Status: completed
Priority: medium
Category: enhancement
Milestone: M3 — Metadata integrity and cache-backed IPTC workflow
Blocked by: 01

## Goal

Prevent TAGGER from submitting an IPTC keyword longer than the IIM 64-byte limit, while preserving a user's rejected input and preventing ExifTool's truncation from losing or desynchronizing metadata.

## Module and Interface

Introduce one Qt-free keyword-limit module as the sole owner of the IPTC constraint. It must expose the normalized UTF-8 byte count and structured over-limit result for a value or an IPTC keyword list. Its normalization is exactly TAGGER's existing keyword normalization: Unicode NFC, then trim outer whitespace. Do not independently reimplement that rule in `MainWindow`, `ResolveKeywordsDialog`, `TagMutationService`, or `ExifTool`.

The module declares `IPTC_KEYWORD_MAX_UTF8_BYTES = 64`. A keyword is valid when `len(normalized.encode("utf-8")) <= 64`; the limit is per keyword, and empty normalized values remain excluded by the existing keyword normalization policy.

`ExifTool.write_keyword_fields()` is the final guard: after normalizing its IPTC arguments and before starting its subprocess, it rejects an invalid IPTC list with a distinct policy error containing the offending normalized value and actual byte count. It never limits XMP-only values. `TagMutationService` must not retry this deterministic policy error; no ExifTool command may run for a rejected target.

## Scope

### Manual Add Keyword field

- On every `addEdit` text change, evaluate the prospective keyword with the shared policy.
- When valid or empty, restore the normal field appearance, hide the keyword-limit warning, and enable Add when the ordinary UI state permits it.
- When over the limit, show the whole `QLineEdit` in its invalid red state, disable Add, and show ordinary-footer feedback with the actual count, for example: `IPTC keyword is 65/64 UTF-8 bytes`.
- The raw text must remain editable. Do not truncate, normalize into the field, clear it, or intercept ordinary text/clipboard input.
- `add_keyword_from_input()` must validate before it clears the field or begins a tag mutation. A rejected Enter, Ctrl+Enter, Add-button, or `:addtag` submission leaves the original field text intact, gives `addEdit` focus, keeps its cursor/selection unchanged, and creates neither a pending mutation nor a recent tag.
- Clear the field only after its valid value has been accepted for queuing, retaining the current successful-add behavior.

### Existing non-manual add routes

- Known-tag activation/double-click validates the selected tag before `_apply_add_tag()`. On failure, do not queue or record it as recent; report the byte-count reason in the footer.
- Yanked-tag paste validates the complete yanked list before it creates intents. If any tag is invalid, reject the paste atomically: queue no tag and identify the invalid value/count in the footer.
- These paths normally contain earlier IPTC values, but must remain protected against malformed externally written metadata.

### Resolve dialog

- Add a non-modal, in-dialog warning label for policy rejections. It must survive row rerenders until the user performs a valid relevant action or cancels; do not use a blocking message box.
- A single XMP-to-IPTC copy (`←`, `h`) validates the source first. If invalid, do not add it to the dialog's IPTC list; leave both lists and the current row selection unchanged and show the warning.
- A whole-list XMP-to-IPTC copy (`<<`, `<<` keyboard operator) preflights all prospective additions. If any value is invalid, copy none of them and report the first invalid value/count. A whole-list operation must not partly apply.
- IPTC-to-XMP copies remain unrestricted by this IPTC rule.
- Apply validates the final IPTC list. On failure it must not accept/close the dialog or enqueue a mutation; it leaves the chosen lists intact and displays the same in-dialog warning.

### Write-boundary behavior

- Every production metadata write currently flows through `ExifTool.write_keyword_fields()`; retain that guard for routine adds, deletes, pastes, Resolve Apply, retries, and future callers. `write_keywords()` delegates to the same protected method.
- If an externally supplied existing IPTC value is already over the limit, any operation whose final IPTC list retains it is rejected before ExifTool. TAGGER must never rewrite such a list and rely on ExifTool truncation. A removal that yields an entirely valid final list remains allowed.
- A deterministic length rejection is validation, not an ExifTool failure: it must not invoke the subprocess, create a backup, or consume Resolve's three write attempts.

## Acceptance Criteria

- Exactly 64 UTF-8 bytes are accepted; 65 are rejected. Tests cover ASCII, multibyte UTF-8, NFC composition, and outer whitespace that is removed before counting.
- An over-limit manual value is visibly invalid while typing; Add is unavailable; submitting it retains raw text, focus, and cursor/selection and starts no mutation or recent-tag update.
- Valid manual input still queues and clears exactly as it did before.
- Known-tag insertion and yanked-tag paste reject invalid input before queueing; a yanked-list rejection is atomic.
- Resolve refuses invalid XMP-to-IPTC single and whole-list copies without altering either candidate list; Apply remains open and unqueued when its final IPTC list is invalid.
- A direct call to `ExifTool.write_keyword_fields()` with an invalid IPTC value raises the distinct policy error before `_run`; an over-limit XMP-only value remains allowed.
- `TagMutationService` does not call ExifTool for a final invalid IPTC target and Resolve does not retry a policy rejection.
- Existing valid behavior for empty XMP preservation, field-specific Resolve choices, pending/failed mutation ordering, and canonical IPTC indexing remains unchanged.

## Out of Scope

- Truncating, auto-abbreviating, or automatically moving a long IPTC keyword to XMP.
- A character-count limit; the contract is UTF-8 bytes.
- Restricting XMP-only keywords.
- Bulk discovery, repair, or automatic normalization of already malformed external IPTC metadata.
- New tag-import or command-argument insertion workflows.

## Tests

- Add focused pure-policy tests for byte counting and violations.
- Extend ExifTool and tag-mutation tests for the final guard and no-retry behavior.
- Extend offscreen MainWindow characterization tests for live manual feedback, rejected submission preservation/focus, Known Tags, and yanked paste.
- Extend Resolve-dialog tests for rejected one-item/all-item XMP-to-IPTC copies and invalid Apply.

## Validation

- Run `ruff format --check` and `ruff check` on modified Python files.
- Run the focused pure-policy, ExifTool, tag-mutation, reconciliation, and offscreen MainWindow tests.
- Run the full `python3 -m unittest` suite and the Windows offscreen acceptance suite.

## Comments

Implemented the shared 64-byte UTF-8 policy, UI preflight paths, Resolve safeguards, and the ExifTool write-boundary guard. Validation completed with Ruff and `python3 -m unittest discover -s tests` (186 tests).
