"""Deterministic fake provider (record/replay style).

Responses come from a committed fixture file, keyed by (model, item_id). This is
what lets the whole gate run in CI with no API key and byte-identical results.

Fixture file shape:

    {
      "version": "1",
      "responses": {
        "<model>": {
          "<item_id>": {
            "text": "...",                # required
            "prompt_tokens": 312,         # optional — omit to simulate a provider
            "completion_tokens": 45,      #   that reports no usage data
            "latency_ms": 820.0,          # optional recorded latency
            "error": "..."                # if present, the call raises ProviderError
          }
        }
      }
    }

A missing (model, item_id) entry raises ProviderError — the same path a real
provider outage takes — so provider-failure behavior is testable offline.
"""

from __future__ import annotations

import math
import os

from ..errors import GateConfigError, ProviderError
from ..loading import _load_json_file
from . import Provider, ProviderRequest, ProviderResult, register_provider


def _validate_fixtures(responses: dict, path: str) -> None:
    """Malformed fixtures must be a clean config error naming the entry — and
    nonsense usage numbers (negative tokens) must never flow into cost totals
    as if they were measured data."""
    for model, items in responses.items():
        if not isinstance(items, dict):
            raise GateConfigError(
                f"fake provider fixtures {path}: entry for model '{model}' must be an object"
            )
        for item_id, entry in items.items():
            where = f"fixtures {path}, model '{model}', item '{item_id}'"
            if not isinstance(entry, dict):
                raise GateConfigError(f"fake provider {where}: entry must be an object")
            for field in ("prompt_tokens", "completion_tokens"):
                value = entry.get(field)
                if value is not None and (
                    not isinstance(value, int) or isinstance(value, bool) or value < 0
                ):
                    raise GateConfigError(
                        f"fake provider {where}: {field} must be a non-negative integer "
                        f"or omitted, got {value!r}"
                    )
            latency = entry.get("latency_ms")
            if latency is not None and (
                not isinstance(latency, (int, float)) or isinstance(latency, bool) or latency < 0
                or not math.isfinite(latency)
            ):
                raise GateConfigError(
                    f"fake provider {where}: latency_ms must be a finite non-negative number "
                    f"or omitted, got {latency!r}"
                )


class FakeProvider(Provider):
    name = "fake"

    def __init__(self, options: dict, base_dir: str):
        fixtures = options.get("fixtures")
        if not isinstance(fixtures, str) or not fixtures:
            raise GateConfigError(
                "fake provider requires provider_options.fixtures (non-empty string path to fixture JSON)"
            )
        path = fixtures if os.path.isabs(fixtures) else os.path.join(base_dir, fixtures)
        data, digest = _load_json_file(path, "fake provider fixture")
        if not isinstance(data, dict) or not isinstance(data.get("responses"), dict):
            raise GateConfigError(f"fake provider fixtures {path}: expected {{'responses': {{...}}}}")
        _validate_fixtures(data["responses"], path)
        self.fixtures_path = path
        # The config-relative reference (what the run config actually wrote). Unlike
        # the resolved absolute path, it is stable across checkout locations, so it is
        # safe to surface in per-item error messages that land in report.json.
        self.fixtures_ref = fixtures
        self.fixtures_sha256 = digest
        self.responses: dict = data["responses"]

    def complete(self, request: ProviderRequest) -> ProviderResult:
        by_model = self.responses.get(request.model)
        if by_model is None:
            raise ProviderError(
                f"no fixtures for model '{request.model}' in {self.fixtures_ref}"
            )
        entry = by_model.get(request.item_id)
        if entry is None:
            raise ProviderError(
                f"no fixture for item '{request.item_id}' under model "
                f"'{request.model}' in {self.fixtures_ref}"
            )
        if "error" in entry:
            raise ProviderError(f"simulated provider failure: {entry['error']}")
        if "text" not in entry:
            raise ProviderError(
                f"fixture for item '{request.item_id}' has neither 'text' nor 'error'"
            )
        if not isinstance(entry["text"], str):
            raise ProviderError(
                f"fixture for item '{request.item_id}' under model "
                f"'{request.model}' in {self.fixtures_ref} has non-string text"
            )
        return ProviderResult(
            text=entry["text"],
            model=request.model,
            prompt_tokens=entry.get("prompt_tokens"),
            completion_tokens=entry.get("completion_tokens"),
            latency_ms=entry.get("latency_ms"),
            raw={"fixture": True},
        )

    def describe(self) -> dict:
        # Identity is the fixtures' CONTENT hash, never their filesystem location:
        # this block is embedded in report.json and folded into result_hash, which
        # must stay path-free so identical inputs hash identically no matter where
        # the repo is checked out (reproducibility contract). The absolute path is
        # volatile and is not part of what produced the verdict; fixtures_sha256 is
        # the reproducible identity, and the manifest already records the config paths.
        return {
            "name": self.name,
            "fixtures_sha256": self.fixtures_sha256,
        }


register_provider("fake", FakeProvider)
