"""Shared policy-input guards for direct callers and stored-evidence audits."""

from __future__ import annotations

import math

from .errors import GateConfigError
from .loading import ThresholdRule, _CONSTRAINT_KEYS, _LEVELS, _UNAVAILABLE_POLICIES, _is_finite_number


def validate_rule(rule: ThresholdRule) -> None:
    if not isinstance(rule, ThresholdRule):
        raise GateConfigError('threshold rule must be a ThresholdRule')
    if not isinstance(rule.metric, str) or not rule.metric:
        raise GateConfigError('threshold metric must be a non-empty string')
    if rule.level not in _LEVELS or rule.on_unavailable not in _UNAVAILABLE_POLICIES:
        raise GateConfigError('threshold level or on_unavailable policy is unsupported')
    if not isinstance(rule.constraints, dict) or not rule.constraints:
        raise GateConfigError('threshold constraints must be a non-empty object')
    for name, value in rule.constraints.items():
        if name not in _CONSTRAINT_KEYS:
            raise GateConfigError('threshold contains an unsupported constraint')
        if not _is_finite_number(value):
            raise GateConfigError('threshold constraints must be finite numbers, not booleans')


def require_number(value: object, label: str) -> int | float:
    # Integers are finite without float conversion, including exact token counts.
    if type(value) is int or (type(value) is float and math.isfinite(value)):
        return value
    raise GateConfigError(f'{label} must be a finite number, not a boolean')
