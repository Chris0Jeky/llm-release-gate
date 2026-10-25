"""Structured-extraction adapter: free text in, one JSON object out.

Item input shape:  {"text": "..."}
Output convention: the reply body is a single JSON object, optionally wrapped
in a ``` / ```json code fence. Anything else is a parse error, which the schema
scorer counts as invalid output (never silently coerced).
"""

from __future__ import annotations

import json
import math
import re

from ..loading import DatasetItem
from . import ParsedOutput, TaskAdapter, register_adapter, require_prompt_str

_FENCE = re.compile(r"^\s*```(?:json)?\s*(.*?)\s*```\s*$", re.DOTALL)


def _reject_constant(name: str):
    raise ValueError(f"non-finite JSON constant {name}")


def _finite_float(literal: str) -> float:
    value = float(literal)
    if not math.isfinite(value):
        raise ValueError(f"non-finite JSON number {literal}")
    return value


def _unique_object(pairs: list[tuple[str, object]]) -> dict:
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise ValueError(f"duplicate key {key!r}")
        obj[key] = value
    return obj


class ExtractionAdapter(TaskAdapter):
    name = "extraction"
    version = "4"  # v4: reject duplicate object keys at every depth
    required_input = ("text",)

    def prompt_fields(self, item: DatasetItem) -> dict[str, str]:
        return {"text": require_prompt_str(item, self.name, "text")}

    def parse(self, text: str, item: DatasetItem) -> ParsedOutput:
        body = text
        fence = _FENCE.match(body)
        if fence:
            body = fence.group(1)
        try:
            obj = json.loads(body, object_pairs_hook=_unique_object,
                             parse_constant=_reject_constant, parse_float=_finite_float)
        except ValueError as exc:
            return ParsedOutput(text=text, parse_error=f"not valid JSON: {exc}")
        return ParsedOutput(text=text, json_obj=obj, has_json=True)


register_adapter("extraction", ExtractionAdapter)
