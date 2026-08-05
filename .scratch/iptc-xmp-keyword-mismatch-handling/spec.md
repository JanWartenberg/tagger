# IPTC/XMP Keyword Mismatch Handling

Status: ready-for-agent
Priority: high

## Problem Statement

TAGGER reads both `IPTC:Keywords` and `XMP-dc:Subject`, displays their merged tags, and warns when their non-empty tag sets differ. The current IPTC-empty filter deliberately uses only `IPTC:Keywords`. The product has no defined policy for the possible mismatch states or for safely resolving them automatically.

## Desired Outcome

Define the meaning of each IPTC/XMP keyword state and a durable policy for detecting, presenting, and resolving mismatches. Any automatic resolution must preserve user intent and never silently discard tags.

## Scope

- Define keyword-field states and their user-visible meaning.
- Define mismatch detection, display, and resolution policy, including whether any automatic resolution is safe.
- Define the relationship between field-specific metadata facts and index-derived features.
- Create separately scoped implementation tickets from the agreed policy.

## Out of Scope

- Implementing the SQLite IPTC-empty crosscheck and `:resync` workflow.
- Defining its verification, result-application, or cache-repair workflow.
- Redefining IPTC-empty as merged-keyword emptiness.
