# First-consumer dogfood scorecard

Use this after selecting `D07-A`. Record actual measurements rather than retrospective impressions.

## Candidate repository criteria

Choose the smallest owned repository that has:

- a real model-backed path;
- a meaningful prompt/model/retrieval/tool change;
- 15–50 representative, non-sensitive initial cases;
- at least one abstention/hallucination or structured-output risk;
- CI where a deliberate regression can be safely blocked.

## Baseline measurements

| Metric | Target/interpretation | Actual |
|---|---|---|
| Time to first green gate | < 90 minutes for owner who knows both repos | |
| Custom glue | < 150 LoC before reusable bridge is justified | |
| Files manually authored | track count; identify confusing duplication | |
| Secrets needed in compare job | zero | |
| Raw sensitive outputs in public surfaces | zero | |
| Deliberate regression blocked | yes | |
| Safe cost-saving candidate allowed | yes | |
| False passes | zero in seeded cases | |
| False blocks | record and classify scorer/policy/data cause | |
| Reviewer comprehension | can explain verdict in < 3 minutes | |
| Snapshot/result reproducibility | identical evidence gives identical hash | |
| PR comment size | below selected deterministic budget | |

## Friction log

For each obstruction, record:

```yaml
id: F-001
observed_at: 2026-..-..
step: capture | import | configure | compare | review | promote
symptom: ...
workaround_minutes: 0
custom_code_lines: 0
repeated_elsewhere: false
candidate_product_change: ...
```

## Decision checkpoint

After the integration, classify every proposed feature:

- **required bridge:** blocks a second credible use;
- **local adapter:** belongs in the consumer repo/example;
- **documentation issue:** no core code needed;
- **speculative platform work:** reject/defer.
