"""Whitespace-only or empty prompt templates are configuration errors."""

from __future__ import annotations

import json

import pytest

from llm_release_gate.errors import GateConfigError
from llm_release_gate.loading import load_run_config


def _write(path, obj) -> str:
    path.write_text(json.dumps(obj), encoding="utf-8")
    return str(path)


def _run_doc(template) -> dict:
    return {
        "provider": "fake",
        "model": "m",
        "prompt": {"template": template},
    }


@pytest.mark.parametrize("bad", ["   ", "\n\t ", ""])
def test_blank_template_rejected(tmp_path, bad):
    path = _write(tmp_path / "run.json", _run_doc(bad))
    with pytest.raises(GateConfigError):
        load_run_config(path, "candidate")


def test_valid_field_template_loads(tmp_path):
    path = _write(tmp_path / "run.json", _run_doc("$question"))
    config = load_run_config(path, "candidate")
    assert config.prompt["template"] == "$question"
