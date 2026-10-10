"""Unknown run/scorer config keys are configuration errors."""

from __future__ import annotations

import json

import pytest

from llm_release_gate.errors import GateConfigError
from llm_release_gate.loading import load_run_config, load_scorer_config


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


def test_run_config_param_typo_rejected_candidate(tmp_path):
    path = _write(tmp_path / "run.json", _run_doc(param={"temperature": 0.9}))
    with pytest.raises(GateConfigError, match="param") as excinfo:
        load_run_config(path, "candidate")
    message = str(excinfo.value)
    assert "param" in message
    assert "allowed keys" in message


def test_run_config_param_typo_rejected_baseline(tmp_path):
    path = _write(tmp_path / "run.json", _run_doc(param={"temperature": 0.9}))
    with pytest.raises(GateConfigError, match="baseline") as excinfo:
        load_run_config(path, "baseline")
    message = str(excinfo.value)
    assert "param" in message
    assert "baseline" in message
    assert "allowed keys" in message


def test_valid_run_config_loads(tmp_path):
    path = _write(
        tmp_path / "run.json",
        {
            "name": "r",
            "provider": "fake",
            "model": "m",
            "params": {"temperature": 0.9},
            "prompt": {"system": "s", "template": "$question"},
            "provider_options": {"fixtures": "f.json"},
        },
    )
    config = load_run_config(path, "candidate")
    assert config.params == {"temperature": 0.9}
    assert config.provider_options == {"fixtures": "f.json"}


def test_scorer_entry_option_typo_rejected(tmp_path):
    path = _write(
        tmp_path / "scorers.json",
        {"scorers": [{"type": "keyword_quality", "option": {"k": 1}}]},
    )
    with pytest.raises(GateConfigError, match=r"scorer #0") as excinfo:
        load_scorer_config(path)
    message = str(excinfo.value)
    assert "option" in message
    assert "scorer #0" in message
    assert "allowed keys" in message


def test_scorer_top_level_typo_rejected(tmp_path):
    path = _write(
        tmp_path / "scorers.json",
        {"scorers": [{"type": "keyword_quality"}], "scorer": []},
    )
    with pytest.raises(GateConfigError, match="scorer") as excinfo:
        load_scorer_config(path)
    message = str(excinfo.value)
    assert "scorer" in message
    assert "allowed keys" in message


def test_valid_scorer_config_with_options_loads(tmp_path):
    path = _write(
        tmp_path / "scorers.json",
        {"scorers": [{"type": "keyword_quality", "options": {"k": 1}}]},
    )
    config = load_scorer_config(path)
    assert config.scorers == [{"type": "keyword_quality", "options": {"k": 1}}]


def test_valid_scorer_config_without_options_loads(tmp_path):
    path = _write(
        tmp_path / "scorers.json", {"scorers": [{"type": "keyword_quality"}]}
    )
    config = load_scorer_config(path)
    assert config.scorers == [{"type": "keyword_quality", "options": {}}]
