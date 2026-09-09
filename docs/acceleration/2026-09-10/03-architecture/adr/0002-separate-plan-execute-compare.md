# ADR 0002: Separate planning, evidence production, and comparison

- **Status:** Proposed
- **Date:** 2026-09-09
- **Related tasks:** I-014, I-015, I-016, I-017, I-019

## Context

The existing `gate` command renders requests, calls a provider, scores results, evaluates policy, and writes reports in one path. This is compact, but it obscures the trust boundary between “what should have been executed,” “what actually executed,” and “how the result was judged.”

## Decision

Introduce three explicit phases while retaining `gate` as a compatibility wrapper:

1. **Plan** — render canonical per-item requests and compute request fingerprints.
2. **Execute/import** — produce an immutable run snapshot whose items reference those fingerprints.
3. **Compare** — validate snapshots, score, calculate cohorts, enforce policy, and render reports without network calls.

Suggested commands:

```text
llm-release-gate plan ... --out plan.json
llm-release-gate capture ... --plan plan.json --out candidate.snapshot.json
llm-release-gate compare --baseline-snapshot ... --candidate-snapshot ...
llm-release-gate gate ...  # compatibility orchestration
```

## Consequences

- The trusted comparator becomes pure and easy to test, fuzz, and embed.
- Imported evidence can be evaluated without adding provider SDKs.
- Failures can be classified as planning, execution/import, or comparison errors.
- More files and schema versions must be documented and migrated.

## Compatibility

- Keep current exit codes: 0 pass, 1 policy regression, 2 could not evaluate.
- `gate` may internally create temporary plan/snapshot artifacts.
- Fixture v1 may be imported only as explicitly marked `legacy-unbound` evidence until request binding is available.
