# 07 — Detect Silently Skipped Malformed IPTC

Status: needs-triage
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
