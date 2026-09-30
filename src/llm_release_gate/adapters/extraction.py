"""Structured-extraction adapter: free text in, one JSON object out.

Item input shape:  {"text": "..."}
Output convention: the reply body is a single JSON object, optionally wrapped
in a ``` / ```json code fence. Anything else is a parse error, which the schema
scorer counts as invalid output (never silently coerced).
"""

from __future__ import annotations

import json
import re

from ..loading import DatasetItem
from . import ParsedOutput, TaskAdapter, register_adapter, require_prompt_str

_FENCE = re.compile(r"^\s*```(?:json)?\s*(.*?)\s*```\s*$", re.DOTALL)


class ExtractionAdapter(TaskAdapter):
    name = "extraction"
    version = "1"
    required_input = ("text",)

    def prompt_fields(self, item: DatasetItem) -> dict[str, str]:
        return {"text": require_prompt_str(item, self.name, "text")}

    def parse(self, text: str, item: DatasetItem) -> ParsedOutput:
        body = text
        fence = _FENCE.match(body)
        if fence:
            body = fence.group(1)
        try:
            obj = json.loads(body)
        except json.JSONDecodeError as exc:
            return ParsedOutput(text=text, parse_error=f"not valid JSON: {exc}")
        return ParsedOutput(text=text, json_obj=obj)


register_adapter("extraction", ExtractionAdapter)
