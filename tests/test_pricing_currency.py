"""USD metrics cannot consume a table priced in another currency (#106)."""

import json

import pytest

from llm_release_gate.cli import main

from conftest import BASE_MODEL, CAND_MODEL, gate_argv


@pytest.mark.parametrize("currency", ["EUR", "GBP", "credits", "usd", "USD ", "USD", None])
def test_gate_requires_usd_pricing(mini_gate, capsys, currency):
    pricing = {"version": "1", "models": {
        model: {"input_per_mtok": 0.95, "output_per_mtok": 0}
        for model in (BASE_MODEL, CAND_MODEL)
    }}
    if currency is not None:
        pricing["currency"] = currency
    response = {"r1": {"text": "anything", "prompt_tokens": 1_000_000, "completion_tokens": 0}}
    paths = mini_gate(
        dataset={"name": "currency", "version": "1", "task": "rag", "items": [{
            "id": "r1", "input": {"question": "q", "documents": []}, "expected": {},
        }]},
        baseline_responses=response, candidate_responses=response, pricing=pricing,
        thresholds={"rules": [{"metric": "cost.total_usd", "max_value": 1}]},
    )
    code = main(gate_argv(paths))
    if currency in ("USD", None):
        assert code == 0
        report = json.loads((paths["tmp"] / "out" / "report.json").read_text(encoding="utf-8"))
        cost = report["metrics"]["cost.total_usd"]["candidate"]
        assert cost["value"] == pytest.approx(0.95)
        assert cost["unit"] == "usd"
    else:
        assert code == 2
        error = capsys.readouterr().err
        assert "configuration error" in error and "currency" in error and "USD" in error
        assert "Traceback" not in error
