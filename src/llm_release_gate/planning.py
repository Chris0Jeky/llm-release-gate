"""Offline request planning. No provider construction, fixture reads or execution."""

from __future__ import annotations

from . import TOOL_NAME, __version__
from .adapters import build_adapter
from .hashing import content_hash
from .errors import GateConfigError
from .loading import Dataset, RunConfig
from .requests import BINDING_SCHEME, request_fingerprint


def build_request_plan(dataset: Dataset, config: RunConfig) -> dict:
    adapter = build_adapter(dataset.task)
    requests = [
        {"item_id": item.id,
         "request_sha256": request_fingerprint(adapter.build_request(item, config))}
        for item in dataset.items
    ]
    plan = {
        "schema_version": "lrg-request-plan/1",
        "tool": {"name": TOOL_NAME, "version": __version__},
        "dataset": {"sha256": dataset.sha256, "task": dataset.task, "n_items": len(requests)},
        "config_sha256": config.sha256,
        "provider": config.provider,
        "adapter": adapter.describe(),
        "request_binding": BINDING_SCHEME,
        "requests": requests,
        "limitations": [
            "Request identities only; no provider was constructed or called.",
            "Hashes do not attest that a model produced any response.",
            "No fixture, scorer, threshold or release verdict was validated.",
        ],
    }
    try:
        plan["plan_hash"] = content_hash(plan)
    except (TypeError, ValueError, RecursionError, UnicodeError) as exc:
        raise GateConfigError("request plan metadata must be finite UTF-8 JSON") from exc
    return plan
