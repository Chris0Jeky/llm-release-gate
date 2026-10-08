"""OSError during open/read surfaces as GateConfigError naming kind and path."""

from __future__ import annotations

import builtins
import json

import pytest

from llm_release_gate.errors import GateConfigError
from llm_release_gate.loading import load_dataset, load_run_config, load_thresholds


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
