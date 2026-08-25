# 01 — Evaluate Practical Multi-Photo Tagging

Status: completed
Priority: medium
Category: product-discovery
Milestone: M4 — Faster photo-finding and tagging workflows
Blocked by: None

## Goal

Assess whether current multi-selection, feedback, and partial-failure behavior supports practical batch tagging.

## Required Triage Before Implementation

- Define representative user workflows and evaluation criteria.
- Identify concrete shortcomings, if any.
- Create separately scoped implementation ticket(s) only for accepted improvements.

## Comments

Created from `BACKLOG.md`. No priority was recorded there.

- The in-memory four-variant UI prototype remains available at [`prototype/multi-photo-tagging-variants.html`](../../../prototype/multi-photo-tagging-variants.html). It explored how to make the batch target, active-photo inspection, and partial-failure retry behavior clear.
- Maintainer decision: do not pursue multi-photo tagging now. The prototype remains a reference artifact.
- Current workaround: copy and paste tags for repeated tagging. This is an acceptable quick, low-complexity solution for now.
- Revisit only if repeated real-world batch-tagging friction demonstrates that copy/paste is insufficient. That evidence was later observed and is reassessed in [`batch-tagging-workflow-reassessment`](../../batch-tagging-workflow-reassessment/issues/01-evaluate-explicit-selection-scoped-batch-tagging.md); do not infer further work from this historical evaluation alone.
