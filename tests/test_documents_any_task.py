"""Present documents fail closed at load time, regardless of dataset task."""

import json
from pathlib import Path

import pytest

from conftest import gate_argv, write_json
from llm_release_gate.cli import main
from llm_release_gate.errors import GateConfigError
from llm_release_gate.loading import load_dataset


@pytest.mark.parametrize("documents,field", [
    (None, "input.documents"),
    ("oops", "input.documents"),
    ({"id": "d1", "text": "source"}, "input.documents"),
    (["oops"], "input.documents[0]"),
    ([{"text": "source"}], "input.documents[0].id"),
    ([{"id": " ", "text": "source"}], "input.documents[0].id"),
    ([{"id": "d1"}], "input.documents[0].text"),
    ([{"id": "d1", "text": None}], "input.documents[0].text"),
    ([{"id": "d1", "text": "a"}, {"id": "d1", "text": "b"}],
     "input.documents[1].id"),
])
def test_non_grounded_documents_rejected_by_loader(tmp_path, documents, field):
    path = write_json(tmp_path / "dataset.json", {
        "name": "extraction-documents", "version": "1", "task": "extraction",
        "items": [{"id": "e1", "input": {"text": "source", "documents": documents}}],
    })
    with pytest.raises(GateConfigError) as excinfo:
        load_dataset(path)
    message = str(excinfo.value)
    assert path in message
    assert "item #0 'e1'" in message
    assert f"field '{field}'" in message


@pytest.mark.parametrize("item_input", [
    {},
    {"text": "source"},
    {"text": "source", "documents": []},
    {"text": "source", "documents": [{"id": "d1", "text": "source"}]},
])
def test_non_grounded_optional_documents_accepted(tmp_path, item_input):
    path = write_json(tmp_path / "dataset.json", {
        "name": "extraction-documents", "version": "1", "task": "extraction",
        "items": [{"id": "e1", "input": item_input}],
    })
    assert load_dataset(path).items[0].input == item_input


@pytest.mark.parametrize("documents", ["oops", [{"text": "source"}], ["oops"]])
def test_non_grounded_documents_are_clean_cli_config_error(mini_gate, capsys, documents):
    responses = {"e1": {"text": '{"field": "value"}'}}
    paths = mini_gate(
        dataset={
            "name": "extraction-documents", "version": "1", "task": "extraction",
            "items": [{"id": "e1", "input": {"text": "source", "documents": documents}}],
        },
        baseline_responses=responses,
        candidate_responses=responses,
        scorers={"scorers": [{"type": "citations"}]},
        thresholds={"rules": [{"metric": "citations.valid_rate", "min_value": 1}]},
    )
    for role in ("baseline", "candidate"):
        config = json.loads(Path(paths[role]).read_text(encoding="utf-8"))
        config["prompt"]["template"] = "$text"
        write_json(Path(paths[role]), config)
    assert main(gate_argv(paths)) == 2
    captured = capsys.readouterr()
    assert "configuration error" in captured.err
    assert "item #0 'e1'" in captured.err
    assert "input.documents" in captured.err
    assert "Traceback" not in captured.err + captured.out
    assert not (paths["tmp"] / "out" / "report.json").exists()
