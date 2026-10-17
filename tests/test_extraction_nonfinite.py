"""ExtractionAdapter rejects non-finite JSON constants fail-closed."""

import json
from pathlib import Path

import pytest

from conftest import gate_argv, write_json
from llm_release_gate.adapters.extraction import ExtractionAdapter
from llm_release_gate.cli import main
from llm_release_gate.loading import DatasetItem
from llm_release_gate.scorers.schema import JsonSchemaScorer


def _item() -> DatasetItem:
    return DatasetItem(id="x", input={"text": "t"}, expected={})


@pytest.mark.parametrize(
    "text",
    [
        "NaN",
        "Infinity",
        "-Infinity",
        '{"total": NaN}',
        '```json\n{"total": Infinity}\n```',
        "1e999",
        '{"total": -1e999}',
    ],
)
def test_nonfinite_literals_are_parse_errors(text):
    parsed = ExtractionAdapter().parse(text, _item())
    assert parsed.parse_error
    assert parsed.parse_error.startswith("not valid JSON")
    assert parsed.has_json is False


def test_nan_parse_does_not_pass_number_schema():
    parsed = ExtractionAdapter().parse("NaN", _item())
    result = JsonSchemaScorer({"schema": {"type": "number"}}).score_item(
        _item(), parsed
    )["schema.valid_rate"]
    assert result["passed"] is False


@pytest.mark.parametrize("text", ['{"total": 1.5}', "null", "0"])
def test_finite_json_still_parses(text):
    parsed = ExtractionAdapter().parse(text, _item())
    assert parsed.parse_error is None
    assert parsed.has_json is True


@pytest.mark.parametrize("literal", ["NaN", "Infinity", "-Infinity", "1e999", "-1e999"])
def test_nested_nonfinite_output_cannot_pass_gate(mini_gate, literal):
    paths = mini_gate(
        dataset={"name": "d", "version": "1", "task": "extraction", "items": [
            {"id": "x", "input": {"text": "t"}},
        ]},
        baseline_responses={"x": {"text": "{}"}},
        candidate_responses={"x": {"text": '{"total": {"amounts": [' + literal + ']}}'}},
        scorers={"scorers": [{"type": "json_schema", "options": {"schema": {"type": "object"}}}]},
        thresholds={"rules": [{"metric": "schema.valid_rate", "min_value": 1}]},
    )
    for role in ("baseline", "candidate"):
        config = json.loads(Path(paths[role]).read_text(encoding="utf-8"))
        config["prompt"]["template"] = "$text"
        write_json(Path(paths[role]), config)
    assert main(gate_argv(paths)) == 1
    report = json.loads((Path(paths["out"]) / "report.json").read_text(encoding="utf-8"))
    assert report["metrics"]["schema.valid_rate"]["candidate"]["value"] == 0
    assert report["items"][0]["candidate"]["parse_error"].startswith("not valid JSON")
