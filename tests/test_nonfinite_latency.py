"""Non-finite latency must fail closed, never pass a threshold.

Python's ``json.loads`` accepts bare ``NaN``/``Infinity`` literals, and every
comparison against NaN is False — so a NaN latency used to sail through fixture
validation, be stored as an available metric, and breach no threshold (fail-open).
These tests pin the fail-closed behavior at each layer.
"""

import pytest

from llm_release_gate.cli import main
from llm_release_gate.errors import GateConfigError
from llm_release_gate.metrics import LOWER, scalar_metric
from llm_release_gate.providers.fake import _validate_fixtures
from llm_release_gate.runner import ItemRecord, _aggregate

from conftest import GOOD_RESPONSE, gate_argv


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_scalar_metric_nonfinite_is_unavailable(bad):
    m = scalar_metric(bad, "ms", LOWER)
    assert m["available"] is False
    assert m["value"] is None
    assert m["note"]


def test_scalar_metric_nonfinite_keeps_caller_note():
    m = scalar_metric(float("nan"), "ms", LOWER, note="partial")
    assert m["available"] is False
    assert m["value"] is None
    assert "nan" in m["note"]
    assert "partial" in m["note"]


def test_scalar_metric_finite_unchanged():
    m = scalar_metric(12.5, "ms", LOWER, n=3)
    assert m["available"] is True
    assert m["value"] == 12.5
    assert m["n"] == 3


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_validate_fixtures_rejects_nonfinite_latency(bad):
    with pytest.raises(GateConfigError, match="finite non-negative"):
        _validate_fixtures({"m": {"q1": {"text": "x", "latency_ms": bad}}}, "f.json")


def test_validate_fixtures_accepts_finite_latency():
    _validate_fixtures({"m": {"q1": {"text": "x", "latency_ms": 820.0}}}, "f.json")


def test_nan_latency_candidate_is_config_error(mini_gate):
    # json.dumps(float("nan")) writes a bare NaN literal — the same bytes a real
    # hand-edited fixture file would carry — and mini_gate writes fixtures that way.
    nan_responses = {k: {**v, "latency_ms": float("nan")} for k, v in GOOD_RESPONSE.items()}
    paths = mini_gate(candidate_responses=nan_responses)
    assert main(gate_argv(paths)) == 2


def test_aggregate_nan_latency_is_unavailable():
    records = [
        ItemRecord(item_id="r1", status="ok", text="a", latency_ms=float("nan")),
        ItemRecord(item_id="r2", status="ok", text="b", latency_ms=float("nan")),
    ]
    aggregates = _aggregate(records, scorers=[])
    assert aggregates["latency.p50_ms"]["available"] is False
