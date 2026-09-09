# Project horizon

## Horizon 0 — trust alignment

Repair the known permission issue, align version/licence/release identity, harden malformed inputs and prove package/Action distribution. This makes the existing public surface trustworthy.

## Horizon 1 — evidence integrity

Introduce request fingerprints and immutable run snapshots. Split execution/import from pure comparison, define paired populations and disclosure profiles, publish schemas and migration rules.

This is the highest-leverage product work because it fixes both the stale-fixture correctness gap and the adoption boundary without requiring a provider zoo.

## Horizon 2 — one real consumer

Integrate a controlled real application. Measure the work required to:

- produce baseline/candidate snapshots;
- keep datasets and expected outcomes versioned;
- review reports in a PR;
- update a baseline safely;
- avoid data leakage;
- diagnose false passes/fails.

Only then refine onboarding (`init`, converter example, command executor or first importer).

## Horizon 3 — evidence-triggered growth

| Observed demand | Candidate expansion |
|---|---|
| Large datasets are too slow twice | bounded concurrency, retry budgets, resume |
| Two users already use one external result format | importer for that format |
| Teams dispute small-sample deltas | minimum-N first, then confidence intervals/repeated trials |
| Deterministic scorers mis-rank real candidates twice | pinned LLM-judge scorer with explicit provenance |
| A second out-of-tree extension exists | entry-point plugin loading |
| Repeated requests for trends/history | local result index, then possibly a service |
| Immutable distribution is operationally required | zipapp, signatures, attestations |

## Long-term option

A hosted release-management platform is possible, but it is not the natural next step. The platform line should be crossed only when teams repeatedly need shared history, retention, access control and collaboration. Until then, static artifacts remain an advantage.

## Stop conditions

Pause expansion when:

- no real consumer exists;
- a proposed feature has no measured trigger;
- a feature moves secrets/user data into the trusted core without a privacy decision;
- the change weakens deterministic evidence or unavailable semantics;
- maintenance cost exceeds demonstrated adoption value.
