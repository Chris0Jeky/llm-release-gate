"""OSError during open/read surfaces as GateConfigError naming kind and path."""

from __future__ import annotations

import builtins
import json
from pathlib import Path

import pytest

from conftest import gate_argv
from llm_release_gate.cli import main
from llm_release_gate.errors import GateConfigError
from llm_release_gate.loading import (
    load_dataset,
    load_pricing,
    load_run_config,
    load_scorer_config,
    load_thresholds,
)


@pytest.mark.parametrize(
    "loader,what",
    [
        (load_dataset, "dataset"),
        (lambda path: load_run_config(path, "candidate"), "candidate"),
        (load_thresholds, "thresholds"),
    ],
)
def test_open_permission_error_is_gate_config_error(tmp_path, monkeypatch, loader, what):
    path = tmp_path / "input.json"
    path.write_text("{}", encoding="utf-8")
    real_open = builtins.open

    def failing_open(name, *args, **kwargs):
        if str(name) == str(path):
            raise PermissionError(13, "synthetic permission failure", str(path))
        return real_open(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", failing_open)
    with pytest.raises(GateConfigError) as excinfo:
        loader(str(path))
    message = str(excinfo.value)
    assert str(path) in message
    assert what in message
    assert isinstance(excinfo.value.__cause__, PermissionError)


def _write(path, obj) -> str:
    path.write_text(json.dumps(obj), encoding="utf-8")
    return str(path)


def _run_doc(**overrides) -> dict:
    doc = {
        "provider": "fake",
        "model": "m",
        "prompt": {"template": "$question"},
    }
    doc.update(overrides)
    return doc


def test_run_config_model_int_rejected(tmp_path):
    path = _write(tmp_path / "run.json", _run_doc(model=123))
    with pytest.raises(GateConfigError) as excinfo:
        load_run_config(path, "candidate")
    assert str(tmp_path / "run.json") in str(excinfo.value)


@pytest.mark.parametrize("field", ["provider", "model"])
def test_run_config_provider_model_empty_string_rejected(tmp_path, field):
    path = _write(tmp_path / "run.json", _run_doc(**{field: ""}))
    with pytest.raises(GateConfigError) as excinfo:
        load_run_config(path, "candidate")
    assert str(tmp_path / "run.json") in str(excinfo.value)


@pytest.mark.parametrize(
    "filename,raw,loader,dup_key",
    [
        (
            "dataset.json",
            '{"name": "a", "name": "b", "version": "1", "task": "qa",'
            ' "items": [{"id": "x"}]}',
            load_dataset,
            "name",
        ),
        (
            "scorer.json",
            '{"scorers": [{"type": "a", "type": "b"}]}',
            load_scorer_config,
            "type",
        ),
        (
            "thresholds.json",
            '{"rules": [{"metric": "m", "max_drop_abs": 1, "max_drop_abs": 2}]}',
            load_thresholds,
            "max_drop_abs",
        ),
    ],
)
def test_duplicate_keys_rejected(tmp_path, filename, raw, loader, dup_key):
    path = tmp_path / filename
    path.write_text(raw, encoding="utf-8")
    with pytest.raises(GateConfigError) as excinfo:
        loader(str(path))
    message = str(excinfo.value)
    assert dup_key in message
    assert str(path) in message


@pytest.mark.parametrize("target", [
    "dataset.json", "baseline.json", "candidate.json", "scorers.json",
    "thresholds.json", "pricing.json", "fixtures/baseline.json", "fixtures/candidate.json",
])
def test_all_gate_inputs_reject_duplicate_keys(mini_gate, capsys, target):
    paths = mini_gate()
    path = paths["tmp"] / target
    source = path.read_text(encoding="utf-8")
    path.write_text(source[:-1] + ', "duplicate": 1, "duplicate": 2}', encoding="utf-8")
    assert main(gate_argv(paths)) == 2
    message = capsys.readouterr().err
    assert "duplicate key 'duplicate'" in message
    assert str(path).replace("\\", "/") in message.replace("\\", "/")
    assert not (Path(paths["out"]) / "report.json").exists()


def test_duplicate_error_constraint_cannot_pass_gate(mini_gate, capsys):
    paths = mini_gate(candidate_responses={
        key: {"error": "provider unavailable"} for key in ("r1", "r2", "r3")
    })
    Path(paths["thresholds"]).write_text(
        '{"rules":[{"metric":"errors.error_rate","max_value":0,"max_value":1}]}',
        encoding="utf-8",
    )
    assert main(gate_argv(paths)) == 2
    assert "duplicate key 'max_value'" in capsys.readouterr().err
    assert not (Path(paths["out"]) / "report.json").exists()


@pytest.mark.parametrize("bad_version", [float("inf"), float("-inf"), float("nan")])
def test_dataset_nonfinite_version_rejected(tmp_path, bad_version):
    doc = {"name": "a", "version": bad_version, "task": "qa", "items": [{"id": "x"}]}
    path = _write(tmp_path / "dataset.json", doc)
    with pytest.raises(GateConfigError) as excinfo:
        load_dataset(path)
    assert str(path) in str(excinfo.value)


def test_dataset_overflow_version_rejected(tmp_path):
    path = tmp_path / "dataset.json"
    path.write_text(
        '{"name": "a", "version": 1e999, "task": "qa", "items": [{"id": "x"}]}',
        encoding="utf-8",
    )
    with pytest.raises(GateConfigError) as excinfo:
        load_dataset(str(path))
    assert str(path) in str(excinfo.value)


@pytest.mark.parametrize("bad_version", [float("inf"), float("-inf"), float("nan")])
def test_pricing_nonfinite_version_rejected(tmp_path, bad_version):
    doc = {
        "version": bad_version,
        "models": {"m": {"input_per_mtok": 1, "output_per_mtok": 1}},
    }
    path = _write(tmp_path / "pricing.json", doc)
    with pytest.raises(GateConfigError) as excinfo:
        load_pricing(path)
    assert str(path) in str(excinfo.value)


def test_pricing_overflow_version_rejected(tmp_path):
    path = tmp_path / "pricing.json"
    path.write_text(
        '{"version": 1e999,'
        ' "models": {"m": {"input_per_mtok": 1, "output_per_mtok": 1}}}',
        encoding="utf-8",
    )
    with pytest.raises(GateConfigError) as excinfo:
        load_pricing(str(path))
    assert str(path) in str(excinfo.value)


def _dataset_doc(**overrides) -> dict:
    doc = {"name": "a", "version": "1", "task": "qa", "items": [{"id": "x"}]}
    doc.update(overrides)
    return doc


@pytest.mark.parametrize("field", ["name", "task"])
def test_dataset_whitespace_name_task_rejected(tmp_path, field):
    path = _write(tmp_path / "dataset.json", _dataset_doc(**{field: "   "}))
    with pytest.raises(GateConfigError) as excinfo:
        load_dataset(path)
    assert str(path) in str(excinfo.value)


def test_dataset_whitespace_item_id_rejected(tmp_path):
    path = _write(
        tmp_path / "dataset.json", _dataset_doc(items=[{"id": "   "}])
    )
    with pytest.raises(GateConfigError) as excinfo:
        load_dataset(path)
    message = str(excinfo.value)
    assert str(path) in message
    assert "item #0" in message


def test_dataset_whitespace_grounded_doc_id_rejected(tmp_path):
    path = _write(
        tmp_path / "dataset.json",
        _dataset_doc(
            task="rag",
            items=[{"id": "x", "input": {"documents": [{"id": "  ", "text": "t"}]}}],
        ),
    )
    with pytest.raises(GateConfigError) as excinfo:
        load_dataset(path)
    message = str(excinfo.value)
    assert str(path) in message
    assert "item #0" in message
