"""Broken extensions must refuse the run, never shrink its denominator (#105)."""

import pytest

from llm_release_gate.cli import main
from llm_release_gate.errors import GateConfigError
from llm_release_gate.metrics import HIGHER
from llm_release_gate.scorers import Scorer, aggregate_scores, item_result
from llm_release_gate.scorers import _REGISTRY

from conftest import gate_argv


class ExtensionScorer(Scorer):
    name = "extension"
    metrics = {"quality.pass_rate": {"direction": HIGHER, "kind": "rate", "mode": "pass_rate"}}

    def score_item(self, item, output):
        return {"quality.pass_rate": item_result(True, True)}


@pytest.mark.parametrize("bad_scores", [
    {}, None, [],
    {"quality.pass_rate": None},
    {"quality.pass_rate": {"applicable": True}},
    {"quality.pass_rate": {"passed": True}},
    {"quality.pass_rate": item_result(True, None)},
    {"quality.pass_rate": item_result("false", True)},
    {"quality.pass_rate": item_result(1, True)},
    {"quality.pass_rate": item_result(True, 1)},
    {"quality.pass_rate": item_result(False, True)},
    {"quality.pass_rate": item_result(True, True, 42)},
    {"quality.pass_rate": {**item_result(True, True), "extra": True}},
    {"quality.pass_rate": item_result(True, True), "errors.error_rate": item_result(True, True)},
])
def test_gate_rejects_malformed_scorer_output(mini_gate, monkeypatch, capsys, bad_scores):
    class BrokenScorer(ExtensionScorer):
        def score_item(self, item, output):
            return bad_scores if item.id == "r2" else super().score_item(item, output)

    monkeypatch.setitem(_REGISTRY, "extension", BrokenScorer)
    paths = mini_gate(
        scorers={"scorers": [{"type": "extension"}]},
        thresholds={"rules": [{"metric": "quality.pass_rate", "min_value": 1}]},
    )
    assert main(gate_argv(paths)) == 2
    error = capsys.readouterr().err
    assert "configuration error" in error and "scorer 'extension'" in error
    assert "Traceback" not in error


@pytest.mark.parametrize("metric", [
    "errors.error_rate", "tokens.total", "cost.total_usd",
    "latency.p50_ms", "latency.p95_ms", "latency.mean_ms",
])
def test_gate_rejects_scorer_system_metric_ownership(mini_gate, monkeypatch, capsys, metric):
    class SystemScorer(ExtensionScorer):
        metrics = {metric: ExtensionScorer.metrics["quality.pass_rate"]}

        def score_item(self, item, output):
            return {metric: item_result(True, True)}

    monkeypatch.setitem(_REGISTRY, "extension", SystemScorer)
    paths = mini_gate(
        scorers={"scorers": [{"type": "extension"}]},
        thresholds={"rules": [{"metric": "errors.error_rate", "max_value": 0}]},
    )
    assert main(gate_argv(paths)) == 2
    error = capsys.readouterr().err
    assert "system metric" in error and metric in error


def test_aggregate_rejects_missing_declared_score():
    with pytest.raises(GateConfigError, match="quality.pass_rate"):
        aggregate_scores([ExtensionScorer({})], [
            {"quality.pass_rate": item_result(True, True)}, {},
        ])


def test_gate_accepts_explicit_inapplicable_score(mini_gate, monkeypatch):
    class ExplicitScorer(ExtensionScorer):
        def score_item(self, item, output):
            if item.id == "r2":
                return {"quality.pass_rate": item_result(False)}
            return {"quality.pass_rate": {"applicable": True, "passed": True}}

    monkeypatch.setitem(_REGISTRY, "extension", ExplicitScorer)
    paths = mini_gate(
        scorers={"scorers": [{"type": "extension"}]},
        thresholds={"rules": [{"metric": "quality.pass_rate", "min_value": 1}]},
    )
    assert main(gate_argv(paths)) == 0
