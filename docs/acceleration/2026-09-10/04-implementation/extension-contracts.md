# Provider and scorer contract enforcement

## Objective

A custom extension must not silently omit declared metrics, emit undeclared metrics, return malformed values, replace a built-in registration, or smuggle invalid usage data into aggregate policy.

## Registry safety

```python
def register_scorer(name: str, factory) -> None:
    if not isinstance(name, str) or not name:
        raise GateConfigError("scorer name must be a non-empty string")
    if name in _REGISTRY:
        raise GateConfigError(f"scorer {name!r} is already registered")
    _REGISTRY[name] = factory
```

Apply equivalent behaviour to providers and adapters. A future plugin system may add explicit namespacing/override controls; the default remains no replacement.

## Scorer result validation

For each answered item and scorer:

- returned value is a dict;
- keys exactly match the scorer's declared metric keys, unless the interface explicitly permits conditional metrics;
- each item result has exactly `applicable`, `passed`, and optional `detail` fields;
- `applicable` is bool;
- `passed` is bool when applicable and `None` when not applicable;
- `detail` is `None` or a bounded string;
- no scorer owns a system metric such as `errors.error_rate`;
- metric specification has a known direction, kind, and aggregation mode.

```python
def validate_item_scores(scorer, scores: object) -> dict[str, dict]:
    if not isinstance(scores, dict):
        raise GateConfigError(f"scorer {scorer.name!r} returned a non-object result")
    expected = set(scorer.metrics)
    actual = set(scores)
    if actual != expected:
        raise GateConfigError(
            f"scorer {scorer.name!r} returned metrics {sorted(actual)}; expected {sorted(expected)}"
        )
    # validate each item-result shape here
    return scores
```

## Provider result validation

Immediately after `complete`:

- `text` and `model` are strings;
- returned model identity is reconciled with requested/actual provider semantics;
- token counts are non-negative integers and not booleans;
- latency is a finite non-negative number;
- raw metadata is an object and never enters reproducible reports unless explicitly normalized;
- provider exceptions are converted to `ProviderError`; programming errors remain internal exit 2 rather than becoming fabricated provider outputs.

## Tests

Create intentionally broken extensions for every contract violation. Assert a clean exit 2 and no policy pass. Include duplicate registration, missing metric, undeclared metric, `applicable=True/passed=None`, non-string detail, negative usage, NaN latency, wrong result type, and provider returning placeholder text after failure.
