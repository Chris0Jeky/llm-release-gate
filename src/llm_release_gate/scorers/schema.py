"""Schema validity for structured output.

Validates the parsed JSON against a schema given in scorer options:

    {"type": "json_schema", "options": {"schema": {...}}}

Implements a documented SUBSET of JSON Schema (kept dependency-free):
type (object/array/string/number/integer/boolean/null), properties, required,
items, enum, additionalProperties (boolean). The schema is validated against
this subset at scorer construction: any keyword or construct the validator
cannot enforce (minimum, pattern, oneOf, union types, ...) is a configuration
error — silently ignoring it would report schema.valid_rate over checks that
never ran. Anything fancier belongs in a custom scorer — see docs/extending.md.
"""

from __future__ import annotations

from ..adapters import ParsedOutput
from ..errors import GateConfigError
from ..loading import DatasetItem
from ..metrics import HIGHER
from . import Scorer, item_result, json_equal, register_scorer

_TYPES = {
    "object": dict,
    "array": list,
    "string": str,
    "number": (int, float),
    "integer": int,
    "boolean": bool,
    "null": type(None),
}

_ALLOWED_KEYWORDS = {"type", "properties", "required", "items", "enum", "additionalProperties"}


def validate_schema_definition(schema, path: str = "$") -> None:
    """Reject any schema this validator cannot fully enforce. Fail-closed: an
    unsupported keyword must be a config error, not a check that silently
    passes everything."""
    if not isinstance(schema, dict):
        raise GateConfigError(f"json_schema scorer: schema at {path} must be an object")
    unknown = set(schema) - _ALLOWED_KEYWORDS
    if unknown:
        raise GateConfigError(
            f"json_schema scorer: unsupported keyword(s) {sorted(unknown)} at {path}; "
            f"this validator enforces only {sorted(_ALLOWED_KEYWORDS)} — "
            f"use a custom scorer for richer schemas (docs/extending.md)"
        )
    stype = schema.get("type")
    if stype is not None and (not isinstance(stype, str) or stype not in _TYPES):
        raise GateConfigError(
            f"json_schema scorer: unsupported type {stype!r} at {path} "
            f"(union types are not supported; allowed: {sorted(_TYPES)})"
        )
    if "required" in schema and (
        not isinstance(schema["required"], list)
        or not all(isinstance(k, str) for k in schema["required"])
    ):
        raise GateConfigError(f"json_schema scorer: 'required' at {path} must be a list of strings")
    if "enum" in schema and not isinstance(schema["enum"], list):
        raise GateConfigError(f"json_schema scorer: 'enum' at {path} must be a list")
    if "additionalProperties" in schema and not isinstance(schema["additionalProperties"], bool):
        raise GateConfigError(
            f"json_schema scorer: 'additionalProperties' at {path} must be true or false "
            f"(schema-valued additionalProperties is not supported)"
        )
    if "properties" in schema:
        if not isinstance(schema["properties"], dict):
            raise GateConfigError(f"json_schema scorer: 'properties' at {path} must be an object")
        for key, sub in schema["properties"].items():
            validate_schema_definition(sub, f"{path}.{key}")
    if "items" in schema:
        validate_schema_definition(schema["items"], f"{path}[]")


def validate_against_schema(value, schema: dict, path: str = "$") -> list[str]:
    """Return a list of human-readable violations; empty list means valid."""
    errors: list[str] = []
    stype = schema.get("type")
    if stype is not None:
        expected = _TYPES.get(stype)
        if expected is None:
            raise GateConfigError(f"json_schema scorer: unsupported type '{stype}' at {path}")
        # bool is an int subclass in Python; keep JSON semantics strict.
        if isinstance(value, bool) and stype in ("number", "integer"):
            errors.append(f"{path}: expected {stype}, got boolean")
            return errors
        if not isinstance(value, expected):
            errors.append(f"{path}: expected {stype}, got {type(value).__name__}")
            return errors
    if "enum" in schema and not any(json_equal(value, e) for e in schema["enum"]):
        errors.append(f"{path}: value {value!r} not in enum {schema['enum']}")
    if isinstance(value, dict):
        for key in schema.get("required", []):
            if key not in value:
                errors.append(f"{path}: missing required property '{key}'")
        properties = schema.get("properties", {})
        for key, sub in properties.items():
            if key in value:
                errors.extend(validate_against_schema(value[key], sub, f"{path}.{key}"))
        if schema.get("additionalProperties") is False:
            extras = sorted(set(value) - set(properties))
            if extras:
                errors.append(f"{path}: unexpected properties {extras}")
    if isinstance(value, list) and "items" in schema:
        for i, element in enumerate(value):
            errors.extend(validate_against_schema(element, schema["items"], f"{path}[{i}]"))
    return errors


class JsonSchemaScorer(Scorer):
    name = "json_schema"
    version = "3"  # v3: distinguish parsed JSON null from absent JSON
    metrics = {
        "schema.valid_rate": {"direction": HIGHER, "kind": "rate", "mode": "pass_rate"},
    }

    def __init__(self, options: dict):
        super().__init__(options)
        self.schema = self.options.get("schema")
        if not isinstance(self.schema, dict):
            raise GateConfigError("json_schema scorer requires options.schema (an object)")
        validate_schema_definition(self.schema)

    def score_item(self, item: DatasetItem, output: ParsedOutput) -> dict[str, dict]:
        if output.parse_error:
            return {
                "schema.valid_rate": item_result(
                    applicable=True, passed=False,
                    detail=output.parse_error,
                )
            }
        if output.json_obj is None and not output.has_json:
            return {
                "schema.valid_rate": item_result(
                    applicable=True, passed=False,
                    detail="no JSON object in output",
                )
            }
        violations = validate_against_schema(output.json_obj, self.schema)
        return {
            "schema.valid_rate": item_result(
                applicable=True,
                passed=not violations,
                detail="; ".join(violations) or None,
            )
        }


register_scorer("json_schema", JsonSchemaScorer)
