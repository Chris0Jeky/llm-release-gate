"""Grounded-documents shape is fail-closed: malformed input.documents raises GateConfigError."""

from __future__ import annotations

import json

import pytest

from llm_release_gate.adapters import build_adapter
from llm_release_gate.errors import GateConfigError
from llm_release_gate.loading import DatasetItem, load_dataset


def _write(path, obj) -> str:
    path.write_text(json.dumps(obj), encoding="utf-8")
    return str(path)


def _dataset_doc(item_input, item_id="r1", task="rag") -> dict:
    return {
        "name": "d",
        "version": "1",
        "task": task,
        "items": [{"id": item_id, "input": item_input, "expected": {}}],
    }


def test_documents_missing_text_raises_naming_item_id(tmp_path):
    path = _write(
        tmp_path / "dataset.json",
        _dataset_doc(
            {"question": "q", "documents": [{"id": "d1"}]},
            item_id="bad-doc",
        ),
    )
    with pytest.raises(GateConfigError) as excinfo:
        load_dataset(path)
    message = str(excinfo.value)
    assert "bad-doc" in message
    assert "dataset.json" in message or str(path) in message


def test_documents_non_list_raises(tmp_path):
    path = _write(
        tmp_path / "dataset.json",
        _dataset_doc({"question": "q", "documents": "oops"}, item_id="bad-list"),
    )
    with pytest.raises(GateConfigError) as excinfo:
        load_dataset(path)
    message = str(excinfo.value)
    assert "bad-list" in message
    assert "input.documents" in message


def test_documents_missing_id_raises(tmp_path):
    path = _write(
        tmp_path / "dataset.json",
        _dataset_doc(
            {"question": "q", "documents": [{"text": "t"}]},
            item_id="no-id",
        ),
    )
    with pytest.raises(GateConfigError) as excinfo:
        load_dataset(path)
    assert "no-id" in str(excinfo.value)


@pytest.mark.parametrize("task", ["rag", "assistant"])
def test_adapter_prompt_fields_rejects_malformed(task):
    adapter = build_adapter(task)
    bad_text = DatasetItem(
        id="i1", input={"question": "q", "documents": [{"id": "d1"}]}, expected={}
    )
    with pytest.raises(GateConfigError) as excinfo:
        adapter.prompt_fields(bad_text)
    assert "i1" in str(excinfo.value)
    bad_list = DatasetItem(
        id="i2", input={"question": "q", "documents": "oops"}, expected={}
    )
    with pytest.raises(GateConfigError) as excinfo:
        adapter.prompt_fields(bad_list)
    assert "i2" in str(excinfo.value)


def test_valid_documents_still_load_and_render(tmp_path):
    path = _write(
        tmp_path / "dataset.json",
        _dataset_doc(
            {"question": "q", "documents": [{"id": "d1", "text": "t"}]},
            item_id="ok",
        ),
    )
    dataset = load_dataset(path)
    assert dataset.items[0].input["documents"] == [{"id": "d1", "text": "t"}]
    rag = build_adapter("rag").prompt_fields(dataset.items[0])
    assert "[doc:d1]" in rag["documents"]
    assistant = build_adapter("assistant").prompt_fields(dataset.items[0])
    assert "[doc:d1]" in assistant["sources"]
    # absent documents stays allowed and renders as ""
    absent = DatasetItem(id="e1", input={"question": "q"}, expected={})
    assert build_adapter("rag").prompt_fields(absent)["documents"] == ""
