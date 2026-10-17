"""Relative rules require matching item evidence, including timing coverage (#108)."""

import json

import pytest

from llm_release_gate.cli import main

from conftest import GOOD_RESPONSE, gate_argv, write_json


def test_gate_refuses_unpaired_success_cohorts(mini_gate):
    paths = mini_gate(
        dataset={"name": "cohorts", "version": "1", "task": "rag", "items": [
            {"id": key, "input": {"question": "q", "documents": []},
             "expected": {"quality": {"must_contain": ["good"]}}}
            for key in "abcd"
        ]},
        baseline_responses={"a": {"text": "good"}, "b": {"text": "bad"},
                            "c": {"error": "timeout"}, "d": {"error": "timeout"}},
        candidate_responses={"a": {"text": "bad"}, "b": {"text": "bad"},
                             "c": {"text": "good"}, "d": {"text": "good"}},
        scorers={"scorers": [{"type": "keyword_quality"}]},
        thresholds={"rules": [{"metric": "quality.pass_rate", "max_drop_abs": 0}]},
    )
    assert main(gate_argv(paths)) == 1
    report = json.loads((paths["tmp"] / "out" / "report.json").read_text(encoding="utf-8"))
    metric = report["metrics"]["quality.pass_rate"]
    assert metric["baseline"]["value"] == metric["candidate"]["value"] == 0.5
    assert metric["delta"] is None
    check = report["rules"][0]["checks"][0]
    assert check["status"] == "unavailable"
    assert "baseline n=2/4" in check["message"] and "candidate n=4/4" in check["message"]
    assert "'c'" in check["message"] and "'d'" in check["message"]


def test_gate_equal_quality_cohorts_still_pass(mini_gate):
    paths = mini_gate()
    assert main(gate_argv(paths)) == 0


def test_gate_refuses_different_applicable_items_with_equal_counts(mini_gate):
    baseline = {key: dict(value) for key, value in GOOD_RESPONSE.items()}
    candidate = {key: dict(value) for key, value in GOOD_RESPONSE.items()}
    baseline["r2"]["text"] = "I don't know."
    candidate["r1"]["text"] = "I don't know."
    paths = mini_gate(
        baseline_responses=baseline, candidate_responses=candidate,
        thresholds={"rules": [{"metric": "citations.valid_rate", "max_drop_abs": 0}]},
    )
    assert main(gate_argv(paths)) == 1
    report = json.loads((paths["tmp"] / "out" / "report.json").read_text(encoding="utf-8"))
    metric = report["metrics"]["citations.valid_rate"]
    assert metric["baseline"]["denominator"] == metric["candidate"]["denominator"] == 1
    assert report["rules"][0]["checks"][0]["status"] == "unavailable"


@pytest.mark.parametrize("comparative", [False, True])
def test_gate_candidate_floor_keeps_full_scope(mini_gate, comparative):
    baseline = {key: dict(value) for key, value in GOOD_RESPONSE.items()}
    baseline["r2"] = {"error": "timeout"}
    rule = {"metric": "quality.pass_rate", "min_value": 1}
    if comparative:
        rule["max_drop_abs"] = 0
    paths = mini_gate(baseline_responses=baseline, thresholds={"rules": [rule]})
    assert main(gate_argv(paths)) == (1 if comparative else 0)
    report = json.loads((paths["tmp"] / "out" / "report.json").read_text(encoding="utf-8"))
    checks = report["rules"][0]["checks"]
    assert next(c for c in checks if c["constraint"] == "min_value")["status"] == "pass"
    if comparative:
        assert next(c for c in checks if c["constraint"] == "max_drop_abs")["status"] == "unavailable"
    else:
        policy = write_json(paths["tmp"] / "relative-policy.json", {
            "rules": [{"metric": "quality.pass_rate", "max_drop_abs": 0}],
        })
        assert main(["audit", "--bundle", paths["out"], "--thresholds", policy]) == 1


@pytest.mark.parametrize("metric", ["latency.p50_ms", "latency.p95_ms", "latency.mean_ms"])
@pytest.mark.parametrize("timings, exit_code", [([150, None], 1), ([None, None], 1), ([100, 400], 0)])
def test_gate_requires_complete_comparable_latency(mini_gate, metric, timings, exit_code):
    paths = mini_gate(
        dataset={"name": "latencies", "version": "1", "task": "rag", "items": [
            {"id": key, "input": {"question": "q", "documents": []}, "expected": {}}
            for key in ("A", "B")
        ]},
        baseline_responses={"A": {"text": "answer", "latency_ms": 100},
                            "B": {"text": "answer", "latency_ms": 400}},
        candidate_responses={key: {"text": "answer", "latency_ms": latency}
                             for key, latency in zip(("A", "B"), timings)},
        thresholds={"rules": [{"metric": metric, "max_increase_abs": 0}]},
    )
    assert main(gate_argv(paths)) == exit_code
    report = json.loads((paths["tmp"] / "out" / "report.json").read_text(encoding="utf-8"))
    assert report["runs"]["candidate"]["n_errors"] == 0
    check = report["rules"][0]["checks"][0]
    if exit_code:
        assert check["status"] == "unavailable"
        assert "baseline n=2/2" in check["message"]
        assert f"candidate n={sum(t is not None for t in timings)}/2" in check["message"]
        assert "'B'" in check["message"]
        assert report["metrics"][metric]["delta"] is None
    else:
        assert check["status"] == "pass"
