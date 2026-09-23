"""Metric constructors and percentile: pin current behaviour."""

import pytest

from llm_release_gate.metrics import (
    HIGHER,
    LOWER,
    percentile,
    rate_metric,
    scalar_metric,
    unavailable_metric,
)


def test_percentile_p95_of_20_is_19th_sorted_value():
    values = [float(i) for i in range(1, 21)]
    assert percentile(values, 95) == 19.0


def test_percentile_p50_even_count():
    values = [10.0, 20.0, 30.0, 40.0]
    assert percentile(values, 50) == 20.0


def test_percentile_p50_odd_count():
    values = [10.0, 20.0, 30.0, 40.0, 50.0]
    assert percentile(values, 50) == 30.0


def test_percentile_single_value():
    assert percentile([42.0], 50) == 42.0
    assert percentile([42.0], 95) == 42.0


def test_percentile_empty_list_raises_value_error():
    with pytest.raises(ValueError, match="percentile of empty list"):
        percentile([], 50)


def test_rate_metric_zero_denominator_default_note():
    m = rate_metric(0, 0, HIGHER)
    assert m["value"] is None
    assert m["available"] is False
    assert m["numerator"] is None
    assert m["denominator"] is None
    assert m["n"] is None
    assert m["unit"] == "rate"
    assert m["note"] == "no applicable items"


def test_rate_metric_zero_denominator_preserves_caller_note():
    m = rate_metric(0, 0, HIGHER, note="nothing applied")
    assert m["value"] is None
    assert m["available"] is False
    assert m["numerator"] is None
    assert m["denominator"] is None
    assert m["n"] is None
    assert m["note"] == "nothing applied"


def test_rate_metric_normal_denominator():
    m = rate_metric(7, 8, HIGHER)
    assert m["value"] == 7 / 8
    assert m["available"] is True
    assert m["numerator"] == 7
    assert m["denominator"] == 8
    assert m["n"] == 8
    assert m["unit"] == "rate"
    assert m["direction"] == HIGHER
    assert m["kind"] == "rate"
    assert m["note"] is None


def test_rate_metric_zero_numerator_is_available_zero():
    m = rate_metric(0, 5, LOWER)
    assert m["value"] == 0.0
    assert m["available"] is True
    assert m["numerator"] == 0
    assert m["denominator"] == 5
    assert m["n"] == 5


def test_scalar_metric_defaults():
    m = scalar_metric(1.5, "ms", LOWER)
    assert m["value"] == 1.5
    assert m["available"] is True
    assert m["unit"] == "ms"
    assert m["direction"] == LOWER
    assert m["numerator"] is None
    assert m["denominator"] is None
    assert m["n"] is None
    assert m["kind"] == "measured"
    assert m["note"] is None


def test_scalar_metric_explicit_n_kind_note():
    m = scalar_metric(2.5, "usd", LOWER, n=3, kind="recorded", note="partial")
    assert m == {
        "value": 2.5,
        "available": True,
        "unit": "usd",
        "direction": LOWER,
        "numerator": None,
        "denominator": None,
        "n": 3,
        "kind": "recorded",
        "note": "partial",
    }


def test_scalar_metric_zero_value_stays_available():
    m = scalar_metric(0.0, "usd", LOWER)
    assert m["value"] == 0.0
    assert m["available"] is True


def test_unavailable_metric_shape():
    m = unavailable_metric("usd", LOWER, "no token usage")
    assert m == {
        "value": None,
        "available": False,
        "unit": "usd",
        "direction": LOWER,
        "numerator": None,
        "denominator": None,
        "n": None,
        "kind": "measured",
        "note": "no token usage",
    }
