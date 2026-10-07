"""Apply an explicit consumer policy to one integrity-verified aggregate snapshot.

This is not rescoring, original-policy reproduction or producer authentication.
No source paths from the bundle are followed and no evidence files are modified.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

from . import TOOL_NAME, __version__
from .bundles import (
    DEFAULT_MAX_BYTES, _agree, _decode_object, _digest, _object,
    _read_artifact, _verified_bundle_snapshot,
)
from .errors import GateConfigError
from .gate import evaluate_thresholds
from .hashing import content_hash
from .loading import ThresholdRule, Thresholds, _CONSTRAINT_KEYS, input_byte_limit
from .metrics import HIGHER, LOWER
from .policy_validation import require_number, validate_rule

_METRIC_FIELDS = ('value', 'available', 'unit', 'direction', 'numerator',
                  'denominator', 'n', 'kind', 'note')


def _metric_view(value: object, label: str) -> dict:
    metric = _object(value, label)
    if any(key not in metric for key in _METRIC_FIELDS):
        raise GateConfigError(f'{label} is missing metric fields')
    if type(metric['available']) is not bool:
        raise GateConfigError(f'{label} available must be boolean')
    if metric['direction'] not in (HIGHER, LOWER):
        raise GateConfigError(f'{label} direction is unsupported')
    for field in ('unit', 'kind'):
        if not isinstance(metric[field], str) or not metric[field]:
            raise GateConfigError(f'{label} {field} must be a non-empty string')
    if metric['note'] is not None and not isinstance(metric['note'], str):
        raise GateConfigError(f'{label} note must be a string or null')
    for field in ('n', 'numerator', 'denominator'):
        count = metric[field]
        if count is not None and (type(count) is not int or count < 0):
            raise GateConfigError(f'{label} {field} must be a non-negative integer or null')
    if metric['available']:
        require_number(metric['value'], label)
        if metric['kind'] in ('rate', 'heuristic_rate'):
            n, d = metric['numerator'], metric['denominator']
            if (type(n) is not int or type(d) is not int or not 0 <= n <= d or d <= 0
                    or metric['n'] != d or metric['unit'] != 'rate' or metric['value'] != n / d):
                raise GateConfigError(f'{label} rate value and counts disagree')
    elif metric['value'] is not None:
        raise GateConfigError(f'{label} unavailable value must be null')
    # Audit output contains standard metric data, not arbitrary extension payloads.
    return {key: metric[key] for key in _METRIC_FIELDS}


def _aggregate_views(report: dict) -> tuple[dict, dict]:
    metrics = _object(report['metrics'], 'report metrics')
    runs = report['runs']
    views = {}
    for side in ('baseline', 'candidate'):
        aggregates = _object(runs[side].get('aggregates'), f'{side} aggregates')
        if set(aggregates) != set(metrics):
            raise GateConfigError(f'{side} aggregate keys disagree with report metrics')
        views[side] = {}
        for key, comparison in metrics.items():
            if not isinstance(key, str) or not key:
                raise GateConfigError('aggregate names must be non-empty strings')
            metric = _object(comparison, f'aggregate {key}').get(side)
            _agree(metric, aggregates[key], f'{side} aggregate {key}')
            views[side][key] = _metric_view(metric, f'{side} aggregate {key}')
    for key in metrics:
        for field in ('unit', 'direction', 'kind'):
            if views['baseline'][key][field] != views['candidate'][key][field]:
                # unavailable_metric intentionally uses generic measured kind.
                if field == 'kind' and not (views['baseline'][key]['available'] and
                                            views['candidate'][key]['available']):
                    continue
                raise GateConfigError(f'aggregate {key} {field} differs between sides')
    return views['baseline'], views['candidate']


def _read_policy(path: str | os.PathLike[str], maximum: int) -> Thresholds:
    with input_byte_limit(maximum):
        try:
            source, _ = _read_artifact(Path(path))
        except GateConfigError as exc:
            raise GateConfigError(f'audit policy: {exc}') from exc
    data = _decode_object(source, 'audit policy')
    entries = data.get('rules')
    if not isinstance(entries, list) or not entries:
        raise GateConfigError('audit policy rules must be a non-empty list')
    allowed = {'metric', 'level', 'on_unavailable', *_CONSTRAINT_KEYS}
    rules = []
    for entry in entries:
        entry = _object(entry, 'audit policy rule')
        if set(entry) - allowed:
            raise GateConfigError('audit policy rule contains unsupported fields')
        rule = ThresholdRule(entry.get('metric'),
            {name: entry[name] for name in _CONSTRAINT_KEYS if name in entry},
            entry.get('level', 'fail'), entry.get('on_unavailable', 'fail'))
        validate_rule(rule)
        rules.append(rule)
    # Exact source bytes match the existing `hash` CLI, not a reserialized policy.
    digest = 'sha256:' + hashlib.sha256(source).hexdigest()
    return Thresholds(rules, str(path), digest, data)


def audit_bundle(
    directory: str | os.PathLike[str], thresholds_path: str | os.PathLike[str], *,
    expected_result_hash: str | None = None, expected_bundle_hash: str | None = None,
    expected_policy_hash: str | None = None, max_input_bytes: int = DEFAULT_MAX_BYTES,
) -> dict:
    """Return a read-only policy audit; its verdict is not the producer's verdict."""
    if expected_policy_hash is not None:
        _digest(expected_policy_hash, 'expected policy hash')
    policy = _read_policy(thresholds_path, max_input_bytes)
    if expected_policy_hash is not None and policy.sha256 != expected_policy_hash:
        raise GateConfigError('expected policy hash does not match the supplied policy')
    proof, report = _verified_bundle_snapshot(
        directory, expected_result_hash=expected_result_hash,
        expected_bundle_hash=expected_bundle_hash, max_input_bytes=max_input_bytes,
    )
    baseline, candidate = _aggregate_views(report)
    rules = evaluate_thresholds(policy, baseline, candidate)
    failed = sum(rule['verdict'] == 'fail' for rule in rules)
    result = {
        'schema_version': 'lrg-policy-audit/1',
        'tool': {'name': TOOL_NAME, 'version': __version__},
        'evaluation_version': '1',
        'basis': 'stored_aggregates',
        'integrity': proof['integrity'],
        'recorded_gate_verdict': proof['gate_verdict'],
        'policy_verdict': 'fail' if failed else 'pass',
        'result_hash': proof['result_hash'],
        'bundle_hash': proof['bundle_hash'],
        'policy_hash': policy.sha256,
        'external_pins': {**proof['external_pins'], 'policy_hash': expected_policy_hash is not None},
        'n_rules': len(rules),
        'n_failed': failed,
        'n_warned': sum(rule['verdict'] == 'warn' for rule in rules),
        'rules': rules,
        'source_inputs_verified': False,
        'scores_recomputed': False,
        'original_policy_recomputed': False,
        'authenticity_verified': False,
        'limitations': [
            'The supplied policy was evaluated against stored aggregates, not recollected or rescored evidence.',
            'Integrity and pins do not prove source truth, model execution, producer authenticity or freshness.',
            'A different consumer policy may accept evidence whose recorded gate failed; both verdicts remain visible.',
        ],
    }
    result['audit_hash'] = content_hash(result)
    return result
