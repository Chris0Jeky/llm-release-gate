# Synthetic request-bound replay

Every response here is hand-authored test data. No model was called and no token,
latency or cost measurement is claimed. Omitted measurements remain unavailable.
The request hashes were constructed with these synthetic responses for this exact
example; this is not a migration of historical or real producer evidence.

Run `make demo-bound` from the repository root. It checks both successful bound
replay and rejection after changing the candidate prompt without changing its
fixtures. It also creates two equivalent offline plans without invoking a provider.

To run the positive gate directly from installed current source:

```bash
python -m llm_release_gate gate \
  --dataset examples/request-bound-replay/dataset.json \
  --baseline examples/request-bound-replay/baseline.json \
  --candidate examples/request-bound-replay/candidate.json \
  --scorers examples/request-bound-replay/scorers.json \
  --thresholds examples/request-bound-replay/thresholds.json \
  --require-request-binding --max-input-bytes 1048576 \
  --out out/new-bound-gate
```

This feature is unreleased main, not the existing tagged Action. See
[the binding contract](../../docs/request-binding.md) for the producer workflow,
exact preimage, compatibility rules and assurance limitations. Matching hashes
do not prove that a model produced an output. Do not transplant these synthetic
outputs or hashes into a real evidence collection.
