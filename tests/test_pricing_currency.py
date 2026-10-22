"""USD metrics cannot consume a table priced in another currency (#106)."""

import json

import pytest

from llm_release_gate.cli import main
from llm_release_gate.errors import GateConfigError
from llm_release_gate.loading import load_pricing

from conftest import BASE_MODEL, CAND_MODEL, gate_argv, write_json


@pytest.mark.parametrize("currency", ["USD", "usd", "Usd", "uSd"])
def test_load_pricing_normalizes_usd_currency(tmp_path, currency):
    path = write_json(tmp_path / "pricing.json", {
        "version": "1", "currency": currency, "models": {},
    })
    assert load_pricing(path).currency == "USD"


@pytest.mark.parametrize("currency", ["EUR", "eur", "Gbp", "credits", "USD "])
def test_load_pricing_rejects_non_usd_currency(tmp_path, currency):
    path = write_json(tmp_path / "pricing.json", {
        "version": "1", "currency": currency, "models": {},
    })
    with pytest.raises(GateConfigError) as error:
        load_pricing(path)
    assert str(error.value) == (
        f"pricing table {path}: 'currency' must be exactly 'USD'; "
        "cost.total_usd does not support currency conversion"
    )


@pytest.mark.parametrize("currency", [
    "EUR", "eur", "GBP", "Gbp", "credits", "usd", "Usd", "uSd", "USD ", "USD", None,
])
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
    if currency in ("USD", "usd", "Usd", "uSd", None):
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
