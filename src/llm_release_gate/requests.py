"""Content identities for rendered requests, not attestations of model execution."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any

from .errors import GateConfigError
from .hashing import content_hash

if TYPE_CHECKING:
    from .providers import ProviderRequest

REQUEST_SCHEMA = "lrg-provider-request/1"
BINDING_SCHEME = "sha256-v1"


def _json_value(value: Any) -> None:
    """Refuse lossy Python-to-JSON coercions in direct library calls."""
    if value is None or type(value) in (str, int, bool):
        return
    if type(value) is float and math.isfinite(value):
        return
    if isinstance(value, dict) and all(isinstance(k, str) for k in value):
        for item in value.values():
            _json_value(item)
        return
    if isinstance(value, list):
        for item in value:
            _json_value(item)
        return
    raise ValueError("expected finite JSON values and string object keys")


def request_fingerprint(request: ProviderRequest) -> str:
    """Hash the exact request under the versioned canonical JSON contract.

    Dictionary key ordering is irrelevant. Text, number spellings after JSON
    parsing (1 vs 1.0), item ID, list ordering and metadata remain significant.
    No file paths, timestamps, expected answers or fixture bytes are added.
    """
    try:
        for field in ("model", "system", "prompt", "item_id"):
            if not isinstance(getattr(request, field), str):
                raise ValueError("request string field has wrong type")
        if not request.model or not request.item_id:
            raise ValueError("request model and item ID must be non-empty")
        if not isinstance(request.params, dict) or not isinstance(request.metadata, dict):
            raise ValueError("request params and metadata must be objects")
        payload = {
            "schema_version": REQUEST_SCHEMA,
            "model": request.model,
            "system": request.system,
            "prompt": request.prompt,
            "params": request.params,
            "item_id": request.item_id,
            "metadata": request.metadata,
        }
        _json_value(payload)
        return content_hash(payload)
    except (ValueError, TypeError, RecursionError, UnicodeError) as exc:
        # Exception details can include supplied values. Never echo request text.
        raise GateConfigError("request cannot be fingerprinted: expected finite JSON "
                              "values, string keys and valid UTF-8 strings") from exc
