"""Metric value representation.

Every aggregate metric is a small dict with a uniform shape so reports and the
threshold engine treat all metrics the same way:

    {
      "value":        float | None,   # None when unavailable
      "available":    bool,
      "unit":         "rate" | "usd" | "ms" | "tokens" | "count",
      "direction":    "higher_better" | "lower_better",
      "numerator":    int | None,     # for rates: how many items counted
      "denominator":  int | None,     # for rates: how many items were applicable
      "n":            int | None,     # for scalars: sample count behind the value
      "kind":         "rate" | "heuristic_rate" | "measured" | "recorded" | "derived",
      "note":         str | None,
    }

Honesty rules encoded here:
- A rate always carries numerator/denominator so reports can print "7/8 (87.5%)".
- ``kind: heuristic_rate`` marks scores produced by keyword/rule heuristics; report
  renderers must never present these as probabilities or model-judged accuracy.
- Unavailable data stays unavailable (value None, available False, note says why).
  Nothing downstream may substitute a default.
"""

from __future__ import annotations

import math
from typing import Optional

HIGHER = "higher_better"
LOWER = "lower_better"


def rate_metric(
    numerator: int,
    denominator: int,
    direction: str,
    kind: str = "rate",
    note: Optional[str] = None,
) -> dict:
    available = denominator > 0
    return {
        "value": (numerator / denominator) if available else None,
        "available": available,
        "unit": "rate",
        "direction": direction,
        "numerator": numerator if available else None,
        "denominator": denominator if available else None,
        "n": denominator if available else None,
        "kind": kind,
        "note": note if available else (note or "no applicable items"),
    }


def scalar_metric(
    value: float,
    unit: str,
    direction: str,
    n: Optional[int] = None,
    kind: str = "measured",
    note: Optional[str] = None,
) -> dict:
    if isinstance(value, float) and not math.isfinite(value):
        reason = f"non-finite value ({value}) reported"
        if note:
            reason = f"{reason}: {note}"
        return unavailable_metric(unit, direction, reason)
    return {
        "value": value,
        "available": True,
        "unit": unit,
        "direction": direction,
        "numerator": None,
        "denominator": None,
        "n": n,
        "kind": kind,
        "note": note,
    }


def unavailable_metric(unit: str, direction: str, note: str) -> dict:
    """A metric whose value could not be computed. The note must say why."""
    return {
        "value": None,
        "available": False,
        "unit": unit,
        "direction": direction,
        "numerator": None,
        "denominator": None,
        "n": None,
        "kind": "measured",
        "note": note,
    }


def percentile(sorted_values: list[float], pct: float) -> float:
    """Nearest-rank percentile (rank = ceil(p/100 * n)) over an already-sorted,
    non-empty list. ceil, not round(): rounding down would systematically
    understate lower-is-better latency percentiles and mask regressions."""
    if not sorted_values:
        raise ValueError("percentile of empty list")
    k = max(1, math.ceil(pct / 100.0 * len(sorted_values)))
    return sorted_values[min(k, len(sorted_values)) - 1]
