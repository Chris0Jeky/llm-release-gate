"""Non-string prompt.system values are configuration errors at load."""

from __future__ import annotations

import json

import pytest

from llm_release_gate.errors import GateConfigError
from llm_release_gate.loading import load_run_config


def _write(path, obj) -> str:
    path.write_text(json.dumps(obj), encoding="utf-8")
    return str(path)


def _run_doc(system) -> dict:
    return {
        "provider": "fake",
        "model": "m",
        "prompt": {"template": "$question", "system": system},
    }


@pytest.mark.parametrize("bad", [123, None, ["system"]])
def test_non_string_system_rejected(tmp_path, bad):
    path = _write(tmp_path / "run.json", _run_doc(bad))
    with pytest.raises(GateConfigError) as excinfo:
        load_run_config(path, "candidate")
    assert "run.json" in str(excinfo.value)


def test_string_system_loads(tmp_path):
    path = _write(tmp_path / "run.json", _run_doc("be helpful"))
    config = load_run_config(path, "candidate")
    assert config.prompt["system"] == "be helpful"


def test_absent_system_loads(tmp_path):
    doc = {
        "provider": "fake",
        "model": "m",
        "prompt": {"template": "$question"},
    }
    path = _write(tmp_path / "run.json", doc)
    config = load_run_config(path, "candidate")
    assert "system" not in config.prompt
