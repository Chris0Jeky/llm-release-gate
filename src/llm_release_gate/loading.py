"""Loading + validation of the five gate inputs.

Each loader returns the parsed object plus a line-ending-normalized sha256 of
the JSON source, so the manifest pins what produced a verdict. Validation
failures raise GateConfigError
(CLI exit 2) with a message naming the file and the problem — a misconfigured
gate must never silently pass.
"""

from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass, field
from typing import Any, Optional

from .errors import GateConfigError
from .hashing import json_source_sha256


def _load_json_file(path: str, what: str) -> tuple[Any, str]:
    if not os.path.isfile(path):
        raise GateConfigError(f"{what} file not found: {path}")
    try:
        with open(path, "rb") as fh:
            source = fh.read()
        data = json.loads(source.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise GateConfigError(f"{what} file is not valid JSON: {path} ({exc})") from exc
    return data, json_source_sha256(source)


def _require(data: dict, key: str, path: str, what: str) -> Any:
    if key not in data:
        raise GateConfigError(f"{what} {path}: missing required key '{key}'")
    return data[key]


def _is_number(value: Any) -> bool:
    """A real JSON number. bool is an int subclass in Python, so a bare
    isinstance(x, (int, float)) is True for True/False; a JSON boolean is never a
    numeric threshold or price and must be rejected, not silently used as 1/0."""
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _is_finite_number(value: Any) -> bool:
    """A JSON number that is also finite (rejects NaN and +/-Infinity)."""
    return _is_number(value) and math.isfinite(value)


# ---------------------------------------------------------------- dataset


@dataclass
class DatasetItem:
    id: str
    input: dict
    expected: dict


@dataclass
class Dataset:
    name: str
    version: str
    task: str
    items: list[DatasetItem]
    path: str
    sha256: str
    raw: dict = field(repr=False, default_factory=dict)


def load_dataset(path: str) -> Dataset:
    data, digest = _load_json_file(path, "dataset")
    if not isinstance(data, dict):
        raise GateConfigError(f"dataset {path}: top level must be a JSON object")
    name = _require(data, "name", path, "dataset")
    version = _require(data, "version", path, "dataset")
    task = _require(data, "task", path, "dataset")
    raw_items = _require(data, "items", path, "dataset")
    if not isinstance(raw_items, list) or not raw_items:
        raise GateConfigError(f"dataset {path}: 'items' must be a non-empty list")
    items: list[DatasetItem] = []
    seen: set[str] = set()
    for i, entry in enumerate(raw_items):
        if not isinstance(entry, dict):
            raise GateConfigError(f"dataset {path}: item #{i} must be an object")
        item_id = entry.get("id")
        if not item_id or not isinstance(item_id, str):
            raise GateConfigError(f"dataset {path}: item #{i} needs a non-empty string 'id'")
        if item_id in seen:
            raise GateConfigError(f"dataset {path}: duplicate item id '{item_id}'")
        seen.add(item_id)
        items.append(
            DatasetItem(
                id=item_id,
                input=entry.get("input", {}),
                expected=entry.get("expected", {}),
            )
        )
    return Dataset(
        name=str(name), version=str(version), task=str(task),
        items=items, path=path, sha256=digest, raw=data,
    )


# ---------------------------------------------------------------- run config


@dataclass
class RunConfig:
    name: str
    provider: str
    model: str
    params: dict
    prompt: dict            # {"system": str, "template": str} — template uses $field
    provider_options: dict  # provider-specific (fake: {"fixtures": path})
    path: str
    sha256: str
    raw: dict = field(repr=False, default_factory=dict)


def load_run_config(path: str, role: str) -> RunConfig:
    data, digest = _load_json_file(path, f"{role} config")
    if not isinstance(data, dict):
        raise GateConfigError(f"{role} config {path}: top level must be a JSON object")
    name = data.get("name") or role
    provider = _require(data, "provider", path, f"{role} config")
    model = _require(data, "model", path, f"{role} config")
    prompt = data.get("prompt", {})
    if not isinstance(prompt, dict):
        raise GateConfigError(f"{role} config {path}: 'prompt' must be an object")
    template = prompt.get("template")
    if not template or not isinstance(template, str):
        raise GateConfigError(
            f"{role} config {path}: prompt.template is required (a $field template; "
            f"see the task adapter for available fields)"
        )
    return RunConfig(
        name=str(name), provider=str(provider), model=str(model),
        params=data.get("params", {}) or {},
        prompt=prompt,
        provider_options=data.get("provider_options", {}) or {},
        path=path, sha256=digest, raw=data,
    )


# ---------------------------------------------------------------- scorer config


@dataclass
class ScorerConfig:
    scorers: list[dict]  # [{"type": str, "options": dict}]
    path: str
    sha256: str
    raw: dict = field(repr=False, default_factory=dict)


def load_scorer_config(path: str) -> ScorerConfig:
    data, digest = _load_json_file(path, "scorer config")
    if not isinstance(data, dict):
        raise GateConfigError(f"scorer config {path}: top level must be a JSON object")
    raw_scorers = _require(data, "scorers", path, "scorer config")
    if not isinstance(raw_scorers, list) or not raw_scorers:
        raise GateConfigError(f"scorer config {path}: 'scorers' must be a non-empty list")
    scorers = []
    for i, entry in enumerate(raw_scorers):
        if not isinstance(entry, dict) or "type" not in entry:
            raise GateConfigError(f"scorer config {path}: scorer #{i} needs a 'type'")
        scorers.append({"type": entry["type"], "options": entry.get("options", {}) or {}})
    return ScorerConfig(scorers=scorers, path=path, sha256=digest, raw=data)


# ---------------------------------------------------------------- thresholds

_CONSTRAINT_KEYS = (
    "max_drop_abs", "max_drop_pct",
    "max_increase_abs", "max_increase_pct",
    "min_value", "max_value",
)
_LEVELS = ("fail", "warn")
_UNAVAILABLE_POLICIES = ("fail", "warn", "skip")


@dataclass
class ThresholdRule:
    metric: str
    constraints: dict           # subset of _CONSTRAINT_KEYS -> number
    level: str = "fail"
    on_unavailable: str = "fail"  # fail-closed: a gate you can't evaluate is a failed gate


@dataclass
class Thresholds:
    rules: list[ThresholdRule]
    path: str
    sha256: str
    raw: dict = field(repr=False, default_factory=dict)


def load_thresholds(path: str) -> Thresholds:
    data, digest = _load_json_file(path, "thresholds")
    if not isinstance(data, dict):
        raise GateConfigError(f"thresholds {path}: top level must be a JSON object")
    raw_rules = _require(data, "rules", path, "thresholds")
    if not isinstance(raw_rules, list) or not raw_rules:
        raise GateConfigError(f"thresholds {path}: 'rules' must be a non-empty list")
    rules: list[ThresholdRule] = []
    for i, entry in enumerate(raw_rules):
        if not isinstance(entry, dict) or "metric" not in entry:
            raise GateConfigError(f"thresholds {path}: rule #{i} needs a 'metric'")
        constraints = {k: entry[k] for k in _CONSTRAINT_KEYS if k in entry}
        if not constraints:
            raise GateConfigError(
                f"thresholds {path}: rule #{i} ({entry['metric']}) has no constraint; "
                f"expected one of {', '.join(_CONSTRAINT_KEYS)}"
            )
        for key, val in constraints.items():
            if not _is_number(val):
                raise GateConfigError(
                    f"thresholds {path}: rule #{i} constraint '{key}' must be a number"
                )
            if not _is_finite_number(val):
                raise GateConfigError(
                    f"thresholds {path}: rule #{i} constraint '{key}' must be a finite number"
                )
        level = entry.get("level", "fail")
        if level not in _LEVELS:
            raise GateConfigError(f"thresholds {path}: rule #{i} level must be one of {_LEVELS}")
        on_unavailable = entry.get("on_unavailable", "fail")
        if on_unavailable not in _UNAVAILABLE_POLICIES:
            raise GateConfigError(
                f"thresholds {path}: rule #{i} on_unavailable must be one of {_UNAVAILABLE_POLICIES}"
            )
        rules.append(
            ThresholdRule(
                metric=str(entry["metric"]), constraints=constraints,
                level=level, on_unavailable=on_unavailable,
            )
        )
    return Thresholds(rules=rules, path=path, sha256=digest, raw=data)


# ---------------------------------------------------------------- pricing


@dataclass
class PricingTable:
    version: str
    currency: str
    models: dict  # model -> {"input_per_mtok": float, "output_per_mtok": float}
    path: Optional[str]
    sha256: Optional[str]
    raw: dict = field(repr=False, default_factory=dict)


def load_pricing(path: str) -> PricingTable:
    data, digest = _load_json_file(path, "pricing table")
    if not isinstance(data, dict):
        raise GateConfigError(f"pricing table {path}: top level must be a JSON object")
    version = _require(data, "version", path, "pricing table")
    models = _require(data, "models", path, "pricing table")
    if not isinstance(models, dict):
        raise GateConfigError(f"pricing table {path}: 'models' must be an object")
    for model, entry in models.items():
        if not isinstance(entry, dict):
            raise GateConfigError(
                f"pricing table {path}: model '{model}' needs numeric "
                f"input_per_mtok and output_per_mtok"
            )
        for key in ("input_per_mtok", "output_per_mtok"):
            rate = entry.get(key)
            if not _is_finite_number(rate) or rate < 0:
                raise GateConfigError(
                    f"pricing table {path}: model '{model}' field '{key}' must be "
                    f"a finite, non-negative number"
                )
    return PricingTable(
        version=str(version), currency=str(data.get("currency", "USD")),
        models=models, path=path, sha256=digest, raw=data,
    )


def no_pricing() -> PricingTable:
    """Used when the caller supplies no pricing table: cost stays unavailable."""
    return PricingTable(version="none", currency="USD", models={}, path=None, sha256=None)
