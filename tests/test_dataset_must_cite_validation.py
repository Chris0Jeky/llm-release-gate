"""Dataset ``expected.must_cite`` ids are validated fail-closed at load time."""

from __future__ import annotations

import json

import pytest

from llm_release_gate.errors import GateConfigError
from llm_release_gate.loading import load_dataset


def _write(path, obj) -> str:
    path.write_text(json.dumps(obj), encoding="utf-8")
    return str(path)


def _dataset_doc(item: dict) -> dict:
    return {"name": "d", "version": "1", "task": "rag", "items": [item]}


def test_must_cite_empty_string_rejected(tmp_path):
    path = _write(
        tmp_path / "dataset.json",
        _dataset_doc({"id": "r1", "input": {}, "expected": {"must_cite": [""]}}),
    )
    with pytest.raises(GateConfigError, match=r"item #0.*r1.*expected\.must_cite"):
        load_dataset(path)


def test_must_cite_whitespace_only_rejected(tmp_path):
    path = _write(
        tmp_path / "dataset.json",
        _dataset_doc({"id": "r1", "input": {}, "expected": {"must_cite": ["   "]}}),
    )
    with pytest.raises(GateConfigError, match=r"item #0.*r1.*expected\.must_cite"):
        load_dataset(path)


def test_must_cite_valid_id_accepted(tmp_path):
    path = _write(
        tmp_path / "dataset.json",
        _dataset_doc({"id": "r1", "input": {}, "expected": {"must_cite": ["d1"]}}),
    )
    dataset = load_dataset(path)
    assert dataset.items[0].expected == {"must_cite": ["d1"]}
