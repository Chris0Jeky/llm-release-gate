# Product positioning

## Recommended one-line position

> A hermetic CI policy gate that turns immutable LLM evaluation evidence into a reproducible, fail-closed release verdict.

## Problem

Teams can run evaluations, but a release still needs an explicit answer to: **is this candidate safe enough to merge under our policy, and can we prove what evidence produced that decision?**

## Wedge

- runs locally or in GitHub Actions;
- accepts versioned evidence from any executor;
- compares baseline and candidate on explicit populations;
- never invents unavailable measurements;
- produces content-addressed JSON, Markdown, HTML and manifests;
- blocks the merge when a policy rule breaches.

## What to claim now

- deterministic offline replay and comparison;
- explicit threshold policy and exit-code contract;
- honest sample counts and unavailable semantics;
- auditable report identity;
- standalone Marketplace Action.

## What not to claim yet

- drop-in observation of arbitrary prompt/model/RAG/tool changes without separately captured evidence;
- statistically significant model evaluation;
- production monitoring;
- complete JSON Schema support;
- provider-agnostic live execution;
- secure handling of sensitive model outputs under default reports.

## Relationship to larger evaluation tools

Do not frame Promptfoo, DeepEval or Braintrust as products to replace. Treat them as potential **evidence producers**. `llm-release-gate` wins by being the small, reviewable policy boundary downstream of execution.

## Defensibility

The practical moat is not scorer count. It is trustworthy semantics:

- request-bound evidence;
- stable schemas and migrations;
- paired-population rules;
- transparent unavailable/coverage handling;
- disclosure-aware reports;
- repeatable release integration.
