"""OSError during open/read surfaces as GateConfigError naming kind and path."""

from __future__ import annotations

import builtins

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
