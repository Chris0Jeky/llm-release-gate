"""Wrongly-typed config fields and non-UTF-8 files are configuration errors."""

from __future__ import annotations

import json

import pytest

from llm_release_gate.errors import GateConfigError
from llm_release_gate.loading import (
    load_dataset,
    load_run_config,
    load_scorer_config,
)


def _write(path, obj) -> str:
    path.write_text(json.dumps(obj), encoding="utf-8")
    return str(path)


def _dataset_doc(item: dict) -> dict:
    return {"name": "d", "version": "1", "task": "rag", "items": [item]}


def _run_doc(**overrides) -> dict:
    doc = {
        "provider": "fake",
        "model": "m",
        "prompt": {"template": "$question"},
    }
    doc.update(overrides)
    return doc


@pytest.mark.parametrize("bad", ["just a string", ["a", "list"], 42])
def test_dataset_input_wrong_type_rejected(tmp_path, bad):
    path = _write(
        tmp_path / "dataset.json",
        _dataset_doc({"id": "r1", "input": bad, "expected": {}}),
    )
    with pytest.raises(GateConfigError, match="must be an object"):
        load_dataset(path)


@pytest.mark.parametrize("bad", ["just a string", ["a", "list"], 42])
def test_dataset_expected_wrong_type_rejected(tmp_path, bad):
    path = _write(
        tmp_path / "dataset.json",
        _dataset_doc({"id": "r1", "input": {}, "expected": bad}),
    )
    with pytest.raises(GateConfigError, match="must be an object"):
        load_dataset(path)


def test_dataset_missing_input_and_expected_default_to_empty(tmp_path):
    path = _write(tmp_path / "dataset.json", _dataset_doc({"id": "r1"}))
    dataset = load_dataset(path)
    assert dataset.items[0].input == {}
    assert dataset.items[0].expected == {}


def test_dataset_non_utf8_bytes_rejected(tmp_path):
    path = tmp_path / "dataset.json"
    path.write_bytes(b'{"name": "d\xe4taset"}')
    with pytest.raises(GateConfigError, match="not valid UTF-8"):
        load_dataset(str(path))


@pytest.mark.parametrize("bad", [["a", "list"], "oops"])
def test_run_config_params_wrong_type_rejected(tmp_path, bad):
    path = _write(tmp_path / "run.json", _run_doc(params=bad))
    with pytest.raises(GateConfigError, match="must be an object"):
        load_run_config(path, "candidate")


def test_run_config_provider_options_wrong_type_rejected(tmp_path):
    path = _write(tmp_path / "run.json", _run_doc(provider_options="oops"))
    with pytest.raises(GateConfigError, match="must be an object"):
        load_run_config(path, "candidate")


def test_run_config_null_params_and_absent_provider_options_default(tmp_path):
    path = _write(tmp_path / "run.json", _run_doc(params=None))
    config = load_run_config(path, "candidate")
    assert config.params == {}
    assert config.provider_options == {}


@pytest.mark.parametrize("bad", [1, ""])
def test_scorer_type_wrong_type_rejected(tmp_path, bad):
    path = _write(tmp_path / "scorers.json", {"scorers": [{"type": bad}]})
    with pytest.raises(GateConfigError, match="must be a non-empty string"):
        load_scorer_config(path)


@pytest.mark.parametrize("bad", ["oops", ["oops"]])
def test_scorer_options_wrong_type_rejected(tmp_path, bad):
    path = _write(
        tmp_path / "scorers.json", {"scorers": [{"type": "keyword_quality", "options": bad}]}
    )
    with pytest.raises(GateConfigError, match="must be an object"):
        load_scorer_config(path)


def test_scorer_null_options_defaults_to_empty(tmp_path):
    path = _write(
        tmp_path / "scorers.json",
        {"scorers": [{"type": "keyword_quality", "options": None}]},
    )
    config = load_scorer_config(path)
    assert config.scorers[0]["options"] == {}
