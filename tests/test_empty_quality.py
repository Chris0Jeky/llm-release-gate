"""An asserted quality block must contain at least one testable check (#113)."""

import json

import pytest

from llm_release_gate.cli import main

from conftest import gate_argv


@pytest.mark.parametrize("quality", [
    {}, {"must_contain": []}, {"must_not_contain": []},
    {"must_contain": [], "must_not_contain": []},
    {"must_contain": [""]}, {"must_not_contain": ["   "]},
])
def test_gate_rejects_empty_quality_assertions(mini_gate, capsys, quality):
    paths = mini_gate(
        dataset={"name": "empty-quality", "version": "1", "task": "rag", "items": [{
            "id": "unasserted", "input": {"question": "Refund policy?", "documents": []},
            "expected": {"quality": quality},
        }]},
        baseline_responses={"unasserted": {"text": "completely unrelated"}},
        candidate_responses={"unasserted": {"text": "completely unrelated"}},
        scorers={"scorers": [{"type": "keyword_quality"}]},
        thresholds={"rules": [{"metric": "quality.pass_rate", "min_value": 1}]},
    )
    assert main(gate_argv(paths)) == 2
    error = capsys.readouterr().err
    assert "configuration error" in error
    assert "unasserted" in error and "expected.quality" in error
    assert "Traceback" not in error


def test_gate_quality_assertion_and_empty_expected_opt_out(mini_gate):
    paths = mini_gate(
        dataset={"name": "quality-control", "version": "1", "task": "rag", "items": [
            {"id": "checked", "input": {"question": "q", "documents": []},
             "expected": {"quality": {"must_contain": ["refund"], "must_not_contain": []}}},
            {"id": "opt-out", "input": {"question": "q", "documents": []}, "expected": {}},
        ]},
        baseline_responses={"checked": {"text": "refund"}, "opt-out": {"text": "anything"}},
        candidate_responses={"checked": {"text": "refund"}, "opt-out": {"text": "anything"}},
        scorers={"scorers": [{"type": "keyword_quality"}]},
        thresholds={"rules": [{"metric": "quality.pass_rate", "min_value": 1}]},
    )
    assert main(gate_argv(paths)) == 0
    report = json.loads((paths["tmp"] / "out" / "report.json").read_text(encoding="utf-8"))
    assert report["metrics"]["quality.pass_rate"]["candidate"]["denominator"] == 1
