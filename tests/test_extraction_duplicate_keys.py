"""Ambiguous extraction replies must not pass by discarding duplicate fields."""

import json
from pathlib import Path

import pytest

from conftest import gate_argv, write_json
from llm_release_gate.adapters.extraction import ExtractionAdapter
from llm_release_gate.cli import main
from llm_release_gate.loading import DatasetItem


@pytest.mark.parametrize("text", [
    '{"approved": false, "approved": true}',
    '{"approved": true, "approved": true}',
    '{"nested": {"approved": false, "approved": true}}',
    '[{"approved": false, "approved": true}]',
    r'{"approved": false, "\u0061pproved": true}',
    '```json\n{"approved": false, "approved": true}\n```',
])
def test_duplicate_keys_are_parse_errors(text):
    parsed = ExtractionAdapter().parse(text, DatasetItem("x", {}, {}))
    assert parsed.parse_error == "not valid JSON: duplicate key 'approved'"
    assert parsed.json_obj is None
    assert parsed.has_json is False
    assert parsed.text == text


@pytest.mark.parametrize("text", [
    '{"approved": true}',
    '{"left": {"approved": false}, "right": {"approved": true}}',
    '[{"approved": false}, {"approved": true}]',
    '{"Approved": false, "approved": true}',
    '```json\n{"approved": true}\n```',
])
def test_distinct_keys_and_separate_objects_still_parse(text):
    parsed = ExtractionAdapter().parse(text, DatasetItem("x", {}, {}))
    assert parsed.parse_error is None
    assert parsed.has_json is True


@pytest.mark.parametrize("scorer,metric", [
    ({"type": "field_match"}, "quality.pass_rate"),
    ({"type": "json_schema", "options": {"schema": {
        "type": "object", "required": ["approved"],
        "properties": {"approved": {"enum": [True]}},
    }}}, "schema.valid_rate"),
])
@pytest.mark.parametrize("duplicate", [False, True])
def test_extraction_gate_rejects_ambiguous_replies(mini_gate, scorer, metric, duplicate):
    candidate = ('{"approved": false, "approved": true}' if duplicate
                 else '{"approved": true}')
    paths = mini_gate(
        dataset={"name": "d", "version": "1", "task": "extraction", "items": [
            {"id": "x", "input": {"text": "source"},
             "expected": {"fields": {"approved": True}}},
        ]},
        baseline_responses={"x": {"text": '{"approved": true}'}},
        candidate_responses={"x": {"text": candidate}},
        scorers={"scorers": [scorer]},
        thresholds={"rules": [{"metric": metric, "min_value": 1}]},
    )
    for role in ("baseline", "candidate"):
        path = Path(paths[role])
        config = json.loads(path.read_text(encoding="utf-8"))
        config["prompt"]["template"] = "$text"
        write_json(path, config)

    assert main(gate_argv(paths)) == int(duplicate)
    report = json.loads((Path(paths["out"]) / "report.json").read_text(encoding="utf-8"))
    assert report["metrics"][metric]["baseline"]["value"] == 1
    assert report["metrics"][metric]["candidate"]["value"] == int(not duplicate)
    assert report["runs"]["candidate"]["n_errors"] == 0
    if duplicate:
        assert "duplicate key" in report["items"][0]["candidate"]["parse_error"]
    assert main(["verify", "--bundle", paths["out"], "--require-pass"]) == int(duplicate)


def test_extraction_adapter_identity_versions_duplicate_key_rejection():
    assert ExtractionAdapter().describe()["version"] == "4"
