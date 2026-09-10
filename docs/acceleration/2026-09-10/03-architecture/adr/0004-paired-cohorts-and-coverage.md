# ADR 0004: Use paired cohorts for relative rules and candidate-wide cohorts for safety floors

- **Status:** Proposed
- **Date:** 2026-09-09
- **Related tasks:** I-018, I-019, I-028

## Context

Independent baseline and candidate aggregates can be computed over different successful/applicable items. A candidate that fails on difficult cases may therefore compare its surviving easy cases with a broader baseline cohort, producing a misleading relative delta.

## Decision

Every metric exposes at least these populations:

- `baseline_all`: all baseline-applicable observations;
- `candidate_all`: all candidate-applicable observations;
- `paired`: observations where both sides are valid and comparable;
- `expected`: the applicable population implied by the dataset/scorer;
- `paired_coverage`: paired / expected.

Policy scope is explicit:

- relative constraints (`max_drop_*`, `max_increase_*`) default to `paired`;
- candidate safety floors/ceilings (`min_value`, `max_value`) default to `candidate_all`;
- provider error rate and answer/completeness coverage remain candidate-wide;
- a `min_coverage` guard can fail or warn before a relative rule is trusted.

## Consequences

- Relative deltas compare like with like.
- Candidate failures cannot improve a score by removing hard items.
- Reports become more verbose because they must show full and paired counts.
- Existing report hashes and schema semantics change and require a documented schema/version transition.

## Edge cases

- Metrics with asymmetric applicability must define what “comparable” means.
- All-pairs-missing is unavailable, not zero.
- Partial latency must not drive a relative verdict without an explicit coverage policy.
- Repeated trials are a later statistical layer and do not change the basic pairing rule.
