"""An explicit null type is a schema configuration error, not an unconstrained type."""

import json
from pathlib import Path

import pytest

from conftest import gate_argv, write_json
from llm_release_gate.adapters.extraction import ExtractionAdapter
from llm_release_gate.cli import main
from llm_release_gate.errors import GateConfigError
from llm_release_gate.loading import DatasetItem
from llm_release_gate.scorers.schema import JsonSchemaScorer, validate_against_schema


@pytest.mark.parametrize("schema,path", [
    ({"type": None}, "$"),
    ({"properties": {"total": {"type": None}}}, "$.total"),
    ({"items": {"type": None}}, "$[]"),
])
def test_explicit_null_type_rejected_at_construction(schema, path):
    with pytest.raises(GateConfigError, match="unsupported type") as excinfo:
        JsonSchemaScorer({"schema": schema})
    assert f"at {path}" in str(excinfo.value)


def test_direct_validation_rejects_explicit_null_type():
    with pytest.raises(GateConfigError, match="unsupported type"):
        validate_against_schema({"unexpected": 123}, {"type": None})


@pytest.mark.parametrize("schema,text,passed", [
    ({}, '{"unexpected": 123}', True),
    ({}, "null", True),
    ({"type": "null"}, "null", True),
    ({"type": "null"}, '{"unexpected": 123}', False),
])
def test_omitted_type_and_null_string_keep_their_meaning(schema, text, passed):
    item = DatasetItem(id="x", input={"text": "t"}, expected={})
    parsed = ExtractionAdapter().parse(text, item)
    result = JsonSchemaScorer({"schema": schema}).score_item(item, parsed)
    assert result["schema.valid_rate"]["passed"] is passed


@pytest.mark.parametrize("schema,exit_code", [
    ({"type": None}, 2),
    ({"properties": {"total": {"type": None}}}, 2),
    ({"type": "null"}, 0),
    ({}, 0),
])
def test_schema_null_type_gate_exit(mini_gate, capsys, schema, exit_code):
    responses = {"x": {"text": "null"}}
    paths = mini_gate(
        dataset={"name": "d", "version": "1", "task": "extraction", "items": [
            {"id": "x", "input": {"text": "t"}},
        ]},
        baseline_responses=responses,
        candidate_responses=responses,
        scorers={"scorers": [{"type": "json_schema", "options": {"schema": schema}}]},
        thresholds={"rules": [{"metric": "schema.valid_rate", "min_value": 1}]},
    )
    for role in ("baseline", "candidate"):
        config = json.loads(Path(paths[role]).read_text(encoding="utf-8"))
        config["prompt"]["template"] = "$text"
        write_json(Path(paths[role]), config)
    assert main(gate_argv(paths)) == exit_code
    if exit_code == 2:
        assert "unsupported type None" in capsys.readouterr().err
        assert not (Path(paths["out"]) / "report.json").exists()
