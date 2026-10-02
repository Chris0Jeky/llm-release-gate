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
import stat
from dataclasses import dataclass, field
from typing import Any, Optional

from .errors import GateConfigError
from .hashing import json_source_sha256


def _open_regular_file(path: str, flags: int) -> int:
    # On POSIX, opening a FIFO can block before fstat can inspect it. Nonblocking
    # open has no effect on regular files; inspect the actual descriptor so a
    # symlink or path replacement cannot bypass the check.
    fd = os.open(path, flags | getattr(os, "O_NONBLOCK", 0))
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise ValueError("expected a regular file")
    except BaseException:
        os.close(fd)
        raise
    return fd


def _load_json_file(path: str, what: str) -> tuple[Any, str]:
    try:
        with open(path, "rb", opener=_open_regular_file) as fh:
            source = fh.read()
    except FileNotFoundError as exc:
        raise GateConfigError(f"{what} file not found: {path}") from exc
    except (OSError, ValueError) as exc:
        raise GateConfigError(f"{what} file could not be read: {path} ({exc})") from exc
    try:
        data = json.loads(source.decode("utf-8"))
    except UnicodeDecodeError as exc:
        raise GateConfigError(f"{what} file is not valid UTF-8: {path} ({exc})") from exc
    except json.JSONDecodeError as exc:
        raise GateConfigError(f"{what} file is not valid JSON: {path} ({exc})") from exc
    except ValueError as exc:
        raise GateConfigError(f"{what} file could not be parsed as JSON: {path} ({exc})") from exc
    except RecursionError as exc:
        raise GateConfigError(f"{what} file exceeds JSON nesting limit: {path} ({exc})") from exc
    return data, json_source_sha256(source)


def _require(data: dict, key: str, path: str, what: str) -> Any:
    if key not in data:
        raise GateConfigError(f"{what} {path}: missing required key '{key}'")
    return data[key]


def _optional_object(data: dict, key: str, where: str) -> dict:
    """An optional object field: absent or null loads as {}; any other
    non-object value is a configuration error naming the location."""
    value = data.get(key, {})
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise GateConfigError(f"{where} '{key}' must be an object")
    return value


def _is_number(value: Any) -> bool:
    """A real JSON number. bool is an int subclass in Python, so a bare
    isinstance(x, (int, float)) is True for True/False; a JSON boolean is never a
    numeric threshold or price and must be rejected, not silently used as 1/0."""
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _is_finite_number(value: Any) -> bool:
    """A JSON number that is also finite as a float (rejects NaN, +/-Infinity, and
    integers too large to convert, which would overflow in the gate arithmetic)."""
    if not _is_number(value):
        return False
    try:
        return math.isfinite(float(value))
    except OverflowError:
        return False


def _normalize_version(value: Any, path: str, what: str) -> str:
    """Keep the released numeric-version coercion while rejecting other JSON types."""
    if isinstance(value, bool) or not isinstance(value, (str, int, float)) or value == "":
        raise GateConfigError(f"{what} {path}: 'version' must be a non-empty string or number")
    return str(value)


def _validate_expected(expected: dict, path: str, i: int, item_id: str) -> None:
    """Fail-closed shape check for a dataset item's ``expected`` block.

    Only applied when a key is PRESENT; absent keys stay allowed and unknown
    extra keys (e.g. ``_note``) stay allowed.
    """
    if "quality" in expected:
        quality = expected["quality"]
        if not isinstance(quality, dict):
            raise GateConfigError(
                f"dataset {path}: item #{i} '{item_id}' field 'expected.quality' must be an object"
            )
        for sub in ("must_contain", "must_not_contain"):
            if sub in quality:
                value = quality[sub]
                if not isinstance(value, list) or any(
                    not isinstance(elt, str) for elt in value
                ):
                    raise GateConfigError(
                        f"dataset {path}: item #{i} '{item_id}' field "
                        f"'expected.quality.{sub}' must be a list of strings"
                    )
    if "must_cite" in expected:
        value = expected["must_cite"]
        if not isinstance(value, list) or any(not isinstance(elt, str) for elt in value):
            raise GateConfigError(
                f"dataset {path}: item #{i} '{item_id}' field 'expected.must_cite' "
                f"must be a list of strings"
            )
    if "should_abstain" in expected:
        if not isinstance(expected["should_abstain"], bool):
            raise GateConfigError(
                f"dataset {path}: item #{i} '{item_id}' field 'expected.should_abstain' "
                f"must be a boolean"
            )
    if "fields" in expected:
        if not isinstance(expected["fields"], dict):
            raise GateConfigError(
                f"dataset {path}: item #{i} '{item_id}' field 'expected.fields' must be an object"
            )


def _validate_grounded_documents(item_input: dict, path: str, i: int, item_id: str) -> None:
    """Fail-closed shape check for ``input.documents`` on grounded tasks.

    Absent stays allowed (adapters render it as ""); when present it must be
    a list of ``{"id", "text"}`` objects with a non-empty string id and
    string text, mirroring the adapter contract so a bad dataset exits 2
    instead of escaping as KeyError/TypeError mid-run.
    """
    if "documents" not in item_input:
        return
    docs = item_input["documents"]
    if not isinstance(docs, list):
        raise GateConfigError(
            f"dataset {path}: item #{i} '{item_id}' field 'input.documents' "
            f"must be a list of objects with string 'id' and 'text'"
        )
    for pos, doc in enumerate(docs):
        if not isinstance(doc, dict):
            raise GateConfigError(
                f"dataset {path}: item #{i} '{item_id}' field "
                f"'input.documents[{pos}]' must be an object with string 'id' and 'text'"
            )
        doc_id = doc.get("id")
        text = doc.get("text")
        if not isinstance(doc_id, str) or not doc_id:
            raise GateConfigError(
                f"dataset {path}: item #{i} '{item_id}' field "
                f"'input.documents[{pos}].id' must be a non-empty string"
            )
        if not isinstance(text, str):
            raise GateConfigError(
                f"dataset {path}: item #{i} '{item_id}' field "
                f"'input.documents[{pos}].text' must be a string"
            )


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
    for _key, _value in (("name", name), ("task", task)):
        if not isinstance(_value, str) or not _value:
            raise GateConfigError(f"dataset {path}: '{_key}' must be a non-empty string")
    version = _normalize_version(version, path, "dataset")
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
        for _key in ("input", "expected"):
            if _key in entry and not isinstance(entry[_key], dict):
                raise GateConfigError(
                    f"dataset {path}: item #{i} '{item_id}' field '{_key}' must be an object"
                )
        if isinstance(entry.get("expected", {}), dict):
            _validate_expected(entry.get("expected", {}), path, i, item_id)
        if task in ("rag", "assistant") and isinstance(entry.get("input", {}), dict):
            _validate_grounded_documents(entry.get("input", {}), path, i, item_id)
        items.append(
            DatasetItem(
                id=item_id,
                input=entry.get("input", {}),
                expected=entry.get("expected", {}),
            )
        )
    return Dataset(
        name=name, version=version, task=task,
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
    if "name" not in data:
        name = role
    else:
        name = data["name"]
        if not isinstance(name, str) or not name:
            raise GateConfigError(f"{role} config {path}: 'name' must be a non-empty string")
    provider = _require(data, "provider", path, f"{role} config")
    if not isinstance(provider, str) or not provider:
        raise GateConfigError(f"{role} config {path}: 'provider' must be a non-empty string")
    model = _require(data, "model", path, f"{role} config")
    if not isinstance(model, str) or not model:
        raise GateConfigError(f"{role} config {path}: 'model' must be a non-empty string")
    prompt = data.get("prompt", {})
    if not isinstance(prompt, dict):
        raise GateConfigError(f"{role} config {path}: 'prompt' must be an object")
    template = prompt.get("template")
    if not isinstance(template, str) or not template.strip():
        raise GateConfigError(
            f"{role} config {path}: prompt.template is required (a $field template; "
            f"see the task adapter for available fields)"
        )
    if "system" in prompt and not isinstance(prompt["system"], str):
        raise GateConfigError(
            f"{role} config {path}: prompt.system must be a string"
        )
    return RunConfig(
        name=name, provider=provider, model=model,
        params=_optional_object(data, "params", f"{role} config {path}"),
        prompt=prompt,
        provider_options=_optional_object(data, "provider_options", f"{role} config {path}"),
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
        scorer_type = entry.get("type") if isinstance(entry, dict) else None
        if not isinstance(scorer_type, str) or not scorer_type:
            raise GateConfigError(f"scorer config {path}: scorer #{i} 'type' must be a non-empty string")
        scorers.append({"type": scorer_type, "options": _optional_object(entry, "options", f"scorer config {path}: scorer #{i}")})
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
        metric = entry["metric"]
        if not isinstance(metric, str) or not metric:
            raise GateConfigError(f"thresholds {path}: rule #{i} 'metric' must be a non-empty string")
        allowed_keys = {"metric", "level", "on_unavailable"} | set(_CONSTRAINT_KEYS)
        unknown_keys = sorted(k for k in entry if k not in allowed_keys)
        if unknown_keys:
            raise GateConfigError(
                f"thresholds {path}: rule #{i} ({entry['metric']}) has unknown key(s): "
                f"{', '.join(unknown_keys)}; allowed keys: {', '.join(sorted(allowed_keys))}"
            )
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
                metric=metric, constraints=constraints,
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
    version = _normalize_version(version, path, "pricing table")
    if "currency" not in data:
        currency = "USD"
    elif not isinstance(data["currency"], str) or not data["currency"]:
        raise GateConfigError(f"pricing table {path}: 'currency' must be a non-empty string")
    else:
        currency = data["currency"]
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
        version=version, currency=currency,
        models=models, path=path, sha256=digest, raw=data,
    )


def no_pricing() -> PricingTable:
    """Used when the caller supplies no pricing table: cost stays unavailable."""
    return PricingTable(version="none", currency="USD", models={}, path=None, sha256=None)
