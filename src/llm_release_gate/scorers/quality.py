"""Answer-quality scorers.

keyword_quality — HEURISTIC. Checks case-insensitive presence/absence of expected
terms. It is a rule-based proxy for correctness, reported as ``heuristic_rate`` and
must never be described as accuracy or a probability. Expected block:

    "expected": {"quality": {"must_contain": ["..."], "must_not_contain": ["..."]}}

field_match — DETERMINISTIC. Exact comparison of extracted JSON fields against
expected values (for structured-extraction tasks):

    "expected": {"fields": {"vendor": "Acme", "total": 1250.5}}

Both emit quality.pass_rate; configure exactly one per gate.
"""

from __future__ import annotations

from ..adapters import ParsedOutput
from ..loading import DatasetItem
from ..metrics import HIGHER
from . import Scorer, item_result, json_equal, register_scorer


class KeywordQualityScorer(Scorer):
    name = "keyword_quality"
    version = "1"
    metrics = {
        "quality.pass_rate": {"direction": HIGHER, "kind": "heuristic_rate", "mode": "pass_rate"},
    }

    def score_item(self, item: DatasetItem, output: ParsedOutput) -> dict[str, dict]:
        spec = item.expected.get("quality")
        # Items expected to abstain are judged by the abstention scorer instead.
        if not spec or item.expected.get("should_abstain"):
            return {"quality.pass_rate": item_result(applicable=False)}
        text = output.text.lower()
        missing = [t for t in spec.get("must_contain", []) if t.lower() not in text]
        forbidden = [t for t in spec.get("must_not_contain", []) if t.lower() in text]
        problems = []
        if missing:
            problems.append(f"missing expected terms: {missing}")
        if forbidden:
            problems.append(f"contains forbidden terms: {forbidden}")
        return {
            "quality.pass_rate": item_result(
                applicable=True,
                passed=not problems,
                detail="; ".join(problems) or None,
            )
        }


class FieldMatchScorer(Scorer):
    name = "field_match"
    version = "3"  # v3: explicit field presence; v2: JSON-strict equality
    metrics = {
        "quality.pass_rate": {"direction": HIGHER, "kind": "rate", "mode": "pass_rate"},
    }

    def score_item(self, item: DatasetItem, output: ParsedOutput) -> dict[str, dict]:
        expected_fields = item.expected.get("fields")
        if not expected_fields:
            return {"quality.pass_rate": item_result(applicable=False)}
        if output.json_obj is None or not isinstance(output.json_obj, dict):
            return {
                "quality.pass_rate": item_result(
                    applicable=True, passed=False,
                    detail=output.parse_error or "output is not a JSON object",
                )
            }
        mismatches = []
        for key, want in expected_fields.items():
            if key not in output.json_obj:
                mismatches.append(f"{key}: field is <missing>")
                continue
            got = output.json_obj[key]
            if not json_equal(got, want):
                mismatches.append(f"{key}: expected {want!r}, got {got!r}")
        return {
            "quality.pass_rate": item_result(
                applicable=True,
                passed=not mismatches,
                detail="; ".join(mismatches) or None,
            )
        }


register_scorer("keyword_quality", KeywordQualityScorer)
register_scorer("field_match", FieldMatchScorer)
