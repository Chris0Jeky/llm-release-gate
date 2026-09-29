"""String-type validation at load, with released numeric-version compatibility."""

from __future__ import annotations

import json

import pytest

from llm_release_gate.errors import GateConfigError
from llm_release_gate.loading import (
    load_dataset,
    load_pricing,
    load_run_config,
    load_thresholds,
)


def _write(path, obj) -> str:
    path.write_text(json.dumps(obj), encoding="utf-8")
    return str(path)


def _dataset_doc(**overrides) -> dict:
    doc = {
        "name": "d",
        "version": "1",
        "task": "rag",
        "items": [{"id": "r1", "input": {}, "expected": {}}],
    }
    doc.update(overrides)
    return doc


def _run_doc(**overrides) -> dict:
    doc = {
        "provider": "fake",
        "model": "m",
        "prompt": {"template": "$question"},
    }
    doc.update(overrides)
    return doc


def test_dataset_name_int_rejected(tmp_path):
    path = _write(tmp_path / "dataset.json", _dataset_doc(name=123))
    with pytest.raises(GateConfigError) as excinfo:
        load_dataset(path)
    assert "dataset.json" in str(excinfo.value)


@pytest.mark.parametrize("bad", [[1], "", None, True])
def test_dataset_version_wrong_type_rejected(tmp_path, bad):
    path = _write(tmp_path / "dataset.json", _dataset_doc(version=bad))
    with pytest.raises(GateConfigError):
        load_dataset(path)


def test_dataset_version_list_rejected(tmp_path):
    path = _write(tmp_path / "dataset.json", _dataset_doc(version=[1]))
    with pytest.raises(GateConfigError):
        load_dataset(path)


@pytest.mark.parametrize("bad", [42, "", None, False])
def test_dataset_task_wrong_type_rejected(tmp_path, bad):
    path = _write(tmp_path / "dataset.json", _dataset_doc(task=bad))
    with pytest.raises(GateConfigError):
        load_dataset(path)


def test_run_config_provider_int_rejected(tmp_path):
    path = _write(tmp_path / "run.json", _run_doc(provider=123))
    with pytest.raises(GateConfigError) as excinfo:
        load_run_config(path, "candidate")
    assert "run.json" in str(excinfo.value)


def test_run_config_model_bool_rejected(tmp_path):
    path = _write(tmp_path / "run.json", _run_doc(model=True))
    with pytest.raises(GateConfigError):
        load_run_config(path, "candidate")


@pytest.mark.parametrize("bad", ["", 123, None, False])
def test_run_config_name_wrong_type_rejected(tmp_path, bad):
    path = _write(tmp_path / "run.json", _run_doc(name=bad))
    with pytest.raises(GateConfigError):
        load_run_config(path, "candidate")


def test_thresholds_metric_int_rejected(tmp_path):
    path = _write(
        tmp_path / "thresholds.json",
        {"rules": [{"metric": 123, "max_drop_abs": 0.1}]},
    )
    with pytest.raises(GateConfigError) as excinfo:
        load_thresholds(path)
    assert "thresholds.json" in str(excinfo.value)


@pytest.mark.parametrize("bad", ["", None, True, ["m"]])
def test_thresholds_metric_wrong_type_rejected(tmp_path, bad):
    path = _write(
        tmp_path / "thresholds.json",
        {"rules": [{"metric": bad, "max_drop_abs": 0.1}]},
    )
    with pytest.raises(GateConfigError):
        load_thresholds(path)


def test_numeric_versions_preserve_released_normalization(tmp_path):
    dataset_path = _write(tmp_path / "dataset.json", _dataset_doc(version=1))
    dataset = load_dataset(dataset_path)
    assert dataset.version == "1"

    path = _write(
        tmp_path / "pricing.json",
        {
            "version": 1,
            "currency": "USD",
            "models": {"m": {"input_per_mtok": 1.0, "output_per_mtok": 2.0}},
        },
    )
    table = load_pricing(path)
    assert table.version == "1"


def test_pricing_currency_bool_rejected(tmp_path):
    path = _write(
        tmp_path / "pricing.json",
        {
            "version": "v1",
            "currency": False,
            "models": {"m": {"input_per_mtok": 1.0, "output_per_mtok": 2.0}},
        },
    )
    with pytest.raises(GateConfigError):
        load_pricing(path)


@pytest.mark.parametrize("bad", ["", 123, None])
def test_pricing_currency_wrong_type_rejected(tmp_path, bad):
    path = _write(
        tmp_path / "pricing.json",
        {
            "version": "v1",
            "currency": bad,
            "models": {"m": {"input_per_mtok": 1.0, "output_per_mtok": 2.0}},
        },
    )
    with pytest.raises(GateConfigError):
        load_pricing(path)


def test_valid_string_inputs_still_load(tmp_path):
    dataset_path = _write(
        tmp_path / "dataset.json",
        _dataset_doc(name="d", version="1", task="rag"),
    )
    dataset = load_dataset(dataset_path)
    assert (dataset.name, dataset.version, dataset.task) == ("d", "1", "rag")

    run_path = _write(
        tmp_path / "run.json",
        _run_doc(name="cand", provider="fake", model="m"),
    )
    config = load_run_config(run_path, "candidate")
    assert (config.name, config.provider, config.model) == ("cand", "fake", "m")

    thresholds_path = _write(
        tmp_path / "thresholds.json",
        {"rules": [{"metric": "quality.pass_rate", "max_drop_abs": 0.1}]},
    )
    thresholds = load_thresholds(thresholds_path)
    assert thresholds.rules[0].metric == "quality.pass_rate"

    pricing_path = _write(
        tmp_path / "pricing.json",
        {
            "version": "v1",
            "currency": "USD",
            "models": {"m": {"input_per_mtok": 1.0, "output_per_mtok": 2.0}},
        },
    )
    table = load_pricing(pricing_path)
    assert (table.version, table.currency) == ("v1", "USD")
