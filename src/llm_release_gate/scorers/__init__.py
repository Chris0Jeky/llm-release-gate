"""Scorer interface, registry and aggregation.

A scorer inspects one item's ParsedOutput against the item's expectations and
emits per-item results for the metrics it owns:

    {"<metric key>": {"applicable": bool, "passed": bool | None, "detail": str | None}}

Aggregation is uniform: for each metric, the rate is computed over *applicable*
items only, and the MetricValue keeps numerator/denominator so reports always
show sample counts next to rates. Two aggregation modes:

- ``pass_rate``:      numerator = items that passed          (direction: higher better)
- ``violation_rate``: numerator = items that violated        (direction: lower better)

Scorers only see items the provider answered; provider failures are counted
separately in errors.error_rate (which the gate checks by default — see gate.py).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Callable

from ..adapters import ParsedOutput
from ..errors import GateConfigError
from ..loading import DatasetItem, ScorerConfig
from ..metrics import rate_metric


def item_result(applicable: bool, passed: bool | None = None, detail: str | None = None) -> dict:
    return {"applicable": applicable, "passed": passed, "detail": detail}


def json_equal(a, b) -> bool:
    """Equality under JSON semantics, structurally at every depth: true != 1 and
    false != 0 (Python's == would conflate them because bool subclasses int),
    while numbers still compare across int/float (310 == 310.0). Lists and dicts
    are compared element-wise so the bool/int distinction also holds inside nested
    values — a top-level-only guard would let {"flags": [1, 0]} match [true, false]."""
    if isinstance(a, bool) or isinstance(b, bool):
        return isinstance(a, bool) and isinstance(b, bool) and a == b
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(json_equal(x, y) for x, y in zip(a, b))
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(json_equal(a[k], b[k]) for k in a)
    return a == b


class Scorer(ABC):
    """Subclasses declare the metrics they own in ``metrics``:
    metric key -> {"direction": ..., "kind": ..., "mode": "pass_rate" | "violation_rate"}"""

    name: str = "abstract"
    version: str = "0"
    metrics: dict[str, dict] = {}

    def __init__(self, options: dict):
        self.options = options or {}

    @abstractmethod
    def score_item(self, item: DatasetItem, output: ParsedOutput) -> dict[str, dict]:
        """Return {metric_key: item_result(...)} for every metric this scorer owns."""

    def describe(self) -> dict:
        return {"name": self.name, "version": self.version, "options": self.options}


_REGISTRY: dict[str, Callable[[dict], Scorer]] = {}

_SYSTEM_METRICS = {
    "errors.error_rate", "tokens.total", "cost.total_usd",
    "latency.p50_ms", "latency.p95_ms", "latency.mean_ms",
}


def validate_item_scores(scorer: Scorer, scores: object) -> dict:
    where = f"scorer '{scorer.name}'"
    if not isinstance(scores, dict) or scores.keys() != scorer.metrics.keys():
        raise GateConfigError(
            f"{where}: item scores must contain exactly the declared metrics "
            f"{list(scorer.metrics)}; got {list(scores) if isinstance(scores, dict) else type(scores).__name__}"
        )
    for key, result in scores.items():
        if (not isinstance(result, dict)
                or not {"applicable", "passed"} <= result.keys()
                or result.keys() - {"applicable", "passed", "detail"}):
            raise GateConfigError(
                f"{where}: '{key}' must be an item result with applicable, passed and optional detail"
            )
        if type(result["applicable"]) is not bool:
            raise GateConfigError(f"{where}: '{key}' applicable must be boolean")
        if ((result["applicable"] and type(result["passed"]) is not bool)
                or (not result["applicable"] and result["passed"] is not None)):
            raise GateConfigError(
                f"{where}: '{key}' passed must be boolean when applicable, otherwise None"
            )
        if result.get("detail") is not None and not isinstance(result["detail"], str):
            raise GateConfigError(f"{where}: '{key}' detail must be a string or None")
    return scores


def register_scorer(name: str, factory: Callable[[dict], Scorer]) -> None:
    _REGISTRY[name] = factory


def build_scorers(config: ScorerConfig) -> list[Scorer]:
    scorers: list[Scorer] = []
    owned: dict[str, str] = {}
    for entry in config.scorers:
        stype = entry["type"]
        if stype not in _REGISTRY:
            raise GateConfigError(
                f"unknown scorer type '{stype}'; registered scorers: {sorted(_REGISTRY)}"
            )
        scorer = _REGISTRY[stype](entry["options"])
        for key in scorer.metrics:
            if key in _SYSTEM_METRICS:
                raise GateConfigError(f"scorer '{stype}' cannot own system metric '{key}'")
            if key in owned:
                raise GateConfigError(
                    f"metric '{key}' is emitted by both '{owned[key]}' and '{stype}' — "
                    f"each metric must have exactly one owner"
                )
            owned[key] = stype
        scorers.append(scorer)
    return scorers


def aggregate_scores(scorers: list[Scorer], scored_items: list[dict]) -> dict[str, dict]:
    """scored_items: one {metric_key: item_result} dict per successfully-answered item."""
    aggregates: dict[str, dict] = {}
    for scorer in scorers:
        results = [validate_item_scores(
            scorer, {key: r[key] for key in scorer.metrics if key in r}
        ) for r in scored_items]
        for key, spec in scorer.metrics.items():
            applicable = [r[key] for r in results if r[key]["applicable"]]
            denominator = len(applicable)
            if spec["mode"] == "pass_rate":
                numerator = sum(1 for r in applicable if r["passed"])
            elif spec["mode"] == "violation_rate":
                numerator = sum(1 for r in applicable if not r["passed"])
            else:  # pragma: no cover - guarded by scorer authors
                raise GateConfigError(f"scorer '{scorer.name}': unknown mode for '{key}'")
            aggregates[key] = rate_metric(
                numerator, denominator, direction=spec["direction"], kind=spec["kind"]
            )
    return aggregates


# Register built-ins on import.
from . import quality as _quality          # noqa: E402,F401
from . import abstention as _abstention    # noqa: E402,F401
from . import citations as _citations      # noqa: E402,F401
from . import schema as _schema            # noqa: E402,F401
