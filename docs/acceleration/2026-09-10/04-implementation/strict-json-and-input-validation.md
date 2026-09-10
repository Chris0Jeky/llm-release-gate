# Strict JSON and policy-bearing input validation

## Objective

Turn malformed, ambiguous, or non-finite input into a concise `GateConfigError` and exit 2 before any run or verdict is produced.

## Parsing primitives

Python's standard JSON parser accepts `NaN`, `Infinity`, and `-Infinity` unless `parse_constant` rejects them. It also silently keeps the last value for duplicate object keys. Both behaviours are unsuitable for content-addressed policy inputs.

```python
import json
import math
from typing import Any

from .errors import GateConfigError


def _reject_constant(value: str) -> None:
    raise GateConfigError(f"non-standard JSON constant is not allowed: {value}")


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise GateConfigError(f"duplicate JSON object key: {key!r}")
        result[key] = value
    return result


def strict_json_loads(source: bytes, *, what: str, path: str) -> Any:
    try:
        return json.loads(
            source.decode("utf-8"),
            parse_constant=_reject_constant,
            object_pairs_hook=_unique_object,
        )
    except UnicodeDecodeError as exc:
        raise GateConfigError(f"{what} is not valid UTF-8: {path}") from exc
    except json.JSONDecodeError as exc:
        raise GateConfigError(f"{what} is not valid JSON: {path} ({exc})") from exc
```

Keep exception wrapping intentional: do not collapse an already-useful `GateConfigError` into an internal traceback.

## Numeric contract

```python
def require_finite_number(value: object, *, where: str, minimum: float | None = None) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise GateConfigError(f"{where} must be a JSON number")
    number = float(value)
    if not math.isfinite(number):
        raise GateConfigError(f"{where} must be finite")
    if minimum is not None and number < minimum:
        raise GateConfigError(f"{where} must be >= {minimum}")
    return number
```

Apply it to thresholds, prices, provider latency, and any custom provider numeric result. Token counts remain non-negative integers, not floats.

For v0.x, either require `currency == "USD"` or rename every cost metric/formatter to be currency-neutral. The bounded option is to reject non-USD pricing while the public metric remains `cost.total_usd`.

## Shape validation priorities

Validate at load time:

- dataset `name`, `version`, and `task` are non-empty strings;
- each item has object-valued `input` and `expected`;
- grounded documents are a list of objects with unique non-empty string IDs and string text;
- run `params`, `prompt`, and `provider_options` are objects;
- scorer `options` is an object;
- pricing models are non-empty names with finite non-negative input/output rates;
- threshold rules reject unknown keys rather than ignoring misspelled policy;
- constraints that are percentages or maximum tolerated changes are non-negative unless negative semantics are explicitly documented;
- schemas reject incoherent keyword/type combinations where feasible.

## Unknown-key policy

Use allowlists for objects whose fields control safety policy. Dataset payloads and provider-specific `options` may deliberately remain extensible, but threshold rules, pricing entries, and top-level public schemas should reject misspellings.

## Tests

- `NaN`, `Infinity`, `-Infinity`, and overflowing exponent values;
- duplicate keys at top level and nested levels;
- UTF-8 BOM and invalid UTF-8 policy, documented explicitly;
- negative, boolean, string, and non-finite prices/thresholds/latencies;
- `EUR` supplied while metric remains `cost.total_usd`;
- duplicate document IDs and non-object documents;
- unknown threshold key beside one valid constraint;
- all failures return exit 2 with path and field context and write no passing report.
