"""Unknown threshold rule keys are configuration errors."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from llm_release_gate.errors import GateConfigError
from llm_release_gate.loading import load_thresholds


def _write(path: Path, obj: dict) -> str:
    path.write_text(json.dumps(obj), encoding="utf-8")
    return str(path)


def test_valid_constraint_plus_typo_is_unknown_key(tmp_path):
    path = _write(
        tmp_path / "thresholds.json",
        {"rules": [{"metric": "cost.total_usd", "max_drop_abs": 0.05, "max_increse_pct": 25}]},
    )
    with pytest.raises(GateConfigError) as excinfo:
        load_thresholds(path)
    message = str(excinfo.value)
    assert "max_increse_pct" in message
    assert "unknown" in message


def test_misspelled_sole_constraint_names_unknown_key(tmp_path):
    path = _write(
        tmp_path / "thresholds.json",
        {"rules": [{"metric": "cost.total_usd", "max_increse_pct": 25}]},
    )
    with pytest.raises(GateConfigError) as excinfo:
        load_thresholds(path)
    assert "max_increse_pct" in str(excinfo.value)


def test_known_optional_keys_still_load(tmp_path):
    path = _write(
        tmp_path / "thresholds.json",
        {
            "rules": [
                {
                    "metric": "quality.pass_rate",
                    "max_drop_abs": 0.05,
                    "level": "warn",
                    "on_unavailable": "skip",
                }
            ]
        },
    )
    thresholds = load_thresholds(path)
    assert len(thresholds.rules) == 1
    rule = thresholds.rules[0]
    assert rule.metric == "quality.pass_rate"
    assert rule.constraints == {"max_drop_abs": 0.05}
    assert rule.level == "warn"
    assert rule.on_unavailable == "skip"


def test_example_thresholds_still_load():
    root = Path(__file__).resolve().parents[1]
    files = sorted(root.glob("examples/**/thresholds.json"))
    assert files, "expected example thresholds.json files under examples/"
    for file in files:
        thresholds = load_thresholds(str(file))
        assert thresholds.rules
