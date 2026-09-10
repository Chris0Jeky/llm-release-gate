# Paired metric aggregation and coverage guardrails

## Objective

Relative policy must compare baseline and candidate over the same items, while absolute candidate safety constraints continue to evaluate the candidate's full applicable population.

## Data model

Preserve item-level scorer observations long enough to build cohorts:

```python
@dataclass(frozen=True)
class MetricObservation:
    item_id: str
    available: bool
    applicable: bool
    value: float | bool | None
    detail: str | None = None
```

For pass/violation rates, the item value can be a boolean pass result. Scalar metrics such as latency may use numeric observations.

## Cohort builder

```python
def paired_ids(baseline: dict[str, MetricObservation], candidate: dict[str, MetricObservation]) -> list[str]:
    return sorted(
        item_id
        for item_id in baseline.keys() & candidate.keys()
        if baseline[item_id].available
        and candidate[item_id].available
        and baseline[item_id].applicable
        and candidate[item_id].applicable
    )
```

Aggregate separate views:

```json
{
  "baseline_all": {"value": 0.91, "n": 100},
  "candidate_all": {"value": 0.89, "n": 97},
  "paired": {
    "baseline": {"value": 0.92, "n": 95},
    "candidate": {"value": 0.90, "n": 95}
  },
  "coverage": {"paired": 95, "expected": 100, "rate": 0.95}
}
```

## Threshold semantics

Add `scope` and optional sample/coverage guards:

```json
{
  "metric": "quality.pass_rate",
  "scope": "paired",
  "max_drop_abs": 0.02,
  "min_n": 50,
  "min_coverage": 0.95
}
```

- relative constraints require paired scope;
- candidate-only min/max defaults to candidate-wide scope;
- an unmet `min_n` or `min_coverage` follows fail-closed unavailable policy;
- error rate and completeness should have explicit candidate-wide rules;
- partial latency observations must carry coverage and cannot silently stand in for the full run.

## Tests

- candidate fails only hard items and cannot improve relative quality;
- baseline and candidate have different scorer applicability;
- zero paired observations;
- exactly-on-boundary coverage and sample size;
- item ordering does not affect results/hashes;
- duplicate/missing IDs are rejected earlier;
- candidate floor fails even where paired delta passes;
- paired delta fails while candidate-wide average appears safe;
- partial latency is unavailable for policy unless selected coverage rule permits it.
