"""Non-finite and negative numeric validation for thresholds and pricing.

Threshold constraint values and pricing rates arrive via ``json.loads``, which
accepts the non-standard literals ``NaN``, ``Infinity`` and ``-Infinity``.
Those must be configuration errors, not values that poison the run.
"""

from __future__ import annotations

import pytest

from llm_release_gate.errors import GateConfigError
from llm_release_gate.loading import load_pricing, load_thresholds


@pytest.mark.parametrize("literal", ["NaN", "Infinity", "-Infinity"])
def test_thresholds_nonfinite_constraint_rejected(tmp_path, literal):
    path = tmp_path / "thresholds.json"
    path.write_text(
        '{"rules": [{"metric": "quality.pass_rate", "max_drop_abs": %s}]}' % literal,
        encoding="utf-8",
    )
    with pytest.raises(GateConfigError, match="finite number"):
        load_thresholds(str(path))


def test_thresholds_negative_finite_constraint_loads(tmp_path):
    path = tmp_path / "thresholds.json"
    path.write_text(
        '{"rules": [{"metric": "quality.pass_rate", "max_drop_abs": -1}]}',
        encoding="utf-8",
    )
    thresholds = load_thresholds(str(path))
    assert thresholds.rules[0].constraints["max_drop_abs"] == -1


@pytest.mark.parametrize("field", ["input_per_mtok", "output_per_mtok"])
@pytest.mark.parametrize("literal", ["NaN", "Infinity", "-Infinity", "-0.5"])
def test_pricing_nonfinite_or_negative_rate_rejected(tmp_path, field, literal):
    other = "output_per_mtok" if field == "input_per_mtok" else "input_per_mtok"
    path = tmp_path / "pricing.json"
    path.write_text(
        '{"version": "test-1", "currency": "USD", "models": '
        '{"m": {"%s": %s, "%s": 1.0}}}' % (field, literal, other),
        encoding="utf-8",
    )
    with pytest.raises(GateConfigError, match="non-negative"):
        load_pricing(str(path))


def test_pricing_zero_rates_load(tmp_path):
    path = tmp_path / "pricing.json"
    path.write_text(
        '{"version": "test-1", "currency": "USD", "models": '
        '{"m": {"input_per_mtok": 0, "output_per_mtok": 0}}}',
        encoding="utf-8",
    )
    table = load_pricing(str(path))
    assert table.models["m"]["input_per_mtok"] == 0
    assert table.models["m"]["output_per_mtok"] == 0
