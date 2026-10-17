"""Grounded sources need unique IDs within each dataset item."""

import json
from pathlib import Path

import pytest

from conftest import gate_argv, write_json
from llm_release_gate.adapters import build_adapter
from llm_release_gate.cli import main
from llm_release_gate.errors import GateConfigError
from llm_release_gate.loading import DatasetItem, load_dataset


def _item(second_id="policy"):
    return DatasetItem(id="r1", input={
        "question": "How long may I request a refund?",
        "documents": [
            {"id": "policy", "text": "Refunds accepted within 30 days."},
            {"id": second_id, "text": "Refunds are not accepted."},
        ],
    }, expected={"must_cite": ["policy"]})


def _dataset(task, second_id="policy"):
    item = _item(second_id)
    return {"name": "d", "version": "1", "task": task, "items": [
        {"id": item.id, "input": item.input, "expected": item.expected},
    ]}


@pytest.mark.parametrize("task", ["rag", "assistant"])
def test_duplicate_document_ids_rejected_by_loader(tmp_path, task):
    path = write_json(tmp_path / "dataset.json", _dataset(task))
    with pytest.raises(GateConfigError, match="duplicate document id 'policy'") as excinfo:
        load_dataset(path)
    message = str(excinfo.value)
    assert path in message
    assert "r1" in message
    assert "input.documents[1].id" in message


@pytest.mark.parametrize("task", ["rag", "assistant"])
@pytest.mark.parametrize("boundary", ["prompt_fields", "parse"])
def test_direct_adapter_rejects_duplicate_document_ids(task, boundary):
    adapter = build_adapter(task)
    with pytest.raises(GateConfigError, match="duplicate document id 'policy'") as excinfo:
        if boundary == "prompt_fields":
            adapter.prompt_fields(_item())
        else:
            adapter.parse("Refunds accepted within 30 days [doc:policy].", _item())
    assert "r1" in str(excinfo.value)


@pytest.mark.parametrize("task", ["rag", "assistant"])
@pytest.mark.parametrize("second_id,exit_code", [("policy", 2), ("other-policy", 0)])
def test_document_id_gate_exit(mini_gate, capsys, task, second_id, exit_code):
    paths = mini_gate(
        dataset=_dataset(task, second_id),
        baseline_responses={"r1": {"text": "Refunds accepted within 30 days [doc:policy]."}},
        candidate_responses={"r1": {"text": "Refunds accepted within 30 days [doc:policy]."}},
        scorers={"scorers": [{"type": "citations"}]},
        thresholds={"rules": [{"metric": "citations.valid_rate", "min_value": 1}]},
    )
    # The assistant adapter exposes the same documents as $sources.
    if task == "assistant":
        for role in ("baseline", "candidate"):
            config = json.loads(Path(paths[role]).read_text(encoding="utf-8"))
            config["prompt"]["template"] = "$sources\n$question"
            write_json(Path(paths[role]), config)
    assert main(gate_argv(paths)) == exit_code
    if exit_code == 2:
        assert "duplicate document id 'policy'" in capsys.readouterr().err
        assert not (Path(paths["out"]) / "report.json").exists()
