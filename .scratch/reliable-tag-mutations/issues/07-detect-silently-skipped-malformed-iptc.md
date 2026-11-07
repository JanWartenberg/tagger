# 07 — Detect Silently Skipped Malformed IPTC

Status: ready-for-agent
Category: bug
Priority: high

## Independently reproduced — 2026-10-21

Linux, ExifTool 12.57, generated disposable Qt JPEG only. Seed
`IPTC:Keywords=existing-iptc` and `XMP-dc:Subject=existing-xmp`. In the APP13
IPTC payload, replace bytes `1c 02 19 00 0d` with `1c 02 19 ff ff`, leaving the
segment length and keyword payload unchanged. The original keyword bytes remain
in the file; QImage still decodes it.

Production `read_keywords` returns empty IPTC, existing XMP, and both readability
flags true. `add_tag('new', keep_backup=False)` succeeds, replaces both fields
with `['new']`, and removes the old payload strings. No backup is created.
Issue 06's declared-readability guard cannot detect this case.

`exiftool -validate -warning -error -a -G1` reports `Validate: OK`, with no
Warning/Error diagnostic. `exiftool -v -IPTC:Keywords` exposes
`Invalid extended IPTC entry (dataset 2:25, len 65535)` in verbose text. Simply
adding validation is therefore insufficient. Determine a bounded, reliable
mutation-read validation strategy without treating absent IPTC as corruption
or blocking explicit Resolve repairs.

Evidence in this container: `/tmp/tagger-unreadable-probe.py`,
`/tmp/tagger-unreadable-write-probe.py`, generated fixtures under
`/tmp/tagger-unreadable-probe-c74iqi77`. These temporary paths are not durable
artifacts; the construction above is the reproducible recipe.

Malformed source SHA-256:
`5b5c2cfa7d45e963ceddc202b1869f7f03f7b1e8610354a1881584bd65e2fdf3`.
After mutation:
`8d2f97d3de1f4131688c9db41f50e9c96c95ae2384cf9c66d76e5cba50151611`.

Truncated APP13 and truncated JPEG probes also returned readable flags, but their
real writes refused without changing bytes or creating backups. Do not
generalize those refusals to the malformed-IIM case above.

## Acceptance needed

Add a generated real-file regression for this corruption before changing the
reader. Refuse ordinary add/remove/paste/retry without changing bytes/backups;
preserve explicit Resolve choices and readable missing-field behavior. Exercise
both backup settings and record ExifTool-version limitations.

## Implementation and validation — 2026-10-28

The generated real-file regression first failed because ordinary add changed the
malformed JPEG and removed the old payload. Single-photo reads now ask ExifTool
for every raw IPTC block, including duplicates, and check IIM record boundaries.
Invalid lengths, malformed block output and blocks larger than 1 MiB are marked
unreadable. If ExifTool returns IPTC tags without a requested block, or no photo
record, the read also fails closed. The existing ordinary-mutation guard then
refuses the write; explicit Resolve remains a deliberate replacement.

The check is based on the [IPTC IIM data-set framing specification](https://iptc.org/std/IIM/4.2/specification/IIMV4.2.pdf),
not ExifTool's unstable verbose text. It checks extracted record structure, not
metadata semantics. A missing block stays a readable empty field. Batched index
reads remain unchanged; all production mutation paths perform a fresh single-photo
read before writing. The per-block parser is limited to 1 MiB; ExifTool's output
capture itself is not capped. If ExifTool silently omits an entire corrupt block,
the absence cannot be distinguished from genuinely absent IPTC by this check.
It is not a general guarantee against every form of container or metadata damage.

- **Passed:** generated malformed JPEGs with add/remove/paste/failed-intent retry,
  backup off and on, byte/file-set preservation, explicit Resolve, and a corrupt
  second IPTC block after a healthy first block. The focused regression passed
  with ExifTool 12.57 and 13.60 on Linux; other versions remain unverified.
- **Passed:** Linux offscreen pytest: 493 passed, four Windows-only skips and
  33 subtests; Ruff lint and modified Python format checks passed.
- **Passed and inspected:** Linux real-file acceptance report
  `tests/acceptance/reports/20261028T174603.279473Z/report.json`: 18 phases,
  52 passing cases, both backup settings, all child exits zero and cleanup
  verified; both workspaces removed and harness hashes matched. Report SHA-256:
  `1ce155abc894badebc8cd9b43363d52074e410e4b08b256e74be082f9f696b88`.
- **Unrun:** Windows real-file acceptance, Windows sharing-lock and native
  process-cleanup checks for this change. Visual behavior was not changed;
  previous visual acceptance remains valid. No new visual check was required.
