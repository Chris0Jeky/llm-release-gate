"""Versioned report-bundle receipts and read-only, offline integrity verification.

Checks supplied content, not model execution, source authenticity, freshness or
policy correctness. Trusted external pins must come from outside the bundle.
Stored manifest paths are descriptive data and are never followed.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
from collections.abc import Mapping

from . import REPORT_SCHEMA_VERSION, TOOL_NAME
from .errors import GateConfigError
from .hashing import content_hash
from .loading import _open_regular_file, _read_json_source, input_byte_limit
from .outputs import LOCK_NAME

BUNDLE_SCHEMA = 'lrg-report-bundle/1'
REPORT_FILES = ('report.json', 'report.md', 'report.html')
DEFAULT_MAX_BYTES = 16 * 1024 * 1024
_DIGEST = re.compile(r'sha256:[0-9a-f]{64}\Z')


def _digest(value: object, label: str) -> str:
    if not isinstance(value, str) or _DIGEST.fullmatch(value) is None:
        raise GateConfigError(f'{label} must be a lowercase sha256 digest')
    return value


def _object(value: object, label: str) -> dict:
    if not isinstance(value, dict):
        raise GateConfigError(f'{label} must be a JSON object')
    return value


def _canonical_hash(value: object, label: str) -> str:
    try:
        return content_hash(value)
    except (ValueError, TypeError, UnicodeError, RecursionError) as exc:
        raise GateConfigError(f'{label} is not finite UTF-8 JSON') from exc


def build_bundle_receipt(manifest: dict, artifacts: Mapping[str, bytes]) -> dict:
    """Cover the manifest before this receipt is attached, plus exact report bytes."""
    if 'bundle_integrity' in manifest or set(artifacts) != set(REPORT_FILES):
        raise GateConfigError('bundle receipt requires an unsealed manifest and exactly three reports')
    receipt = {
        'schema_version': BUNDLE_SCHEMA,
        'result_hash': _digest(manifest.get('result_hash'), 'manifest result hash'),
        'manifest_sha256': _canonical_hash(manifest, 'manifest'),
        'files': {name: {'sha256': 'sha256:' + hashlib.sha256(artifacts[name]).hexdigest(),
                         'size_bytes': len(artifacts[name])} for name in REPORT_FILES},
    }
    receipt['bundle_hash'] = content_hash(receipt)
    return receipt


class _DuplicateKey(ValueError):
    pass


def _unique_object(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateKey()
        result[key] = value
    return result


def _finite_float(token: str) -> float:
    value = float(token)
    if not math.isfinite(value):
        raise ValueError('non-finite number')
    return value


def _reject_constant(token: str) -> None:
    raise ValueError('non-finite number')


def _decode_object(data: bytes, label: str) -> dict:
    try:
        value = json.loads(data.decode('utf-8'), object_pairs_hook=_unique_object,
                           parse_float=_finite_float, parse_constant=_reject_constant)
    except _DuplicateKey as exc:
        raise GateConfigError(f'{label} contains duplicate JSON object keys') from exc
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise GateConfigError(f'{label} is not valid finite UTF-8 JSON') from exc
    _object(value, label)
    _canonical_hash(value, label)  # Also rejects lone Unicode surrogates.
    return value


def _signature(info: os.stat_result) -> tuple:
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_mode


def _read_artifact(path: Path) -> tuple[bytes, tuple]:
    try:
        initial = path.lstat()
        if not stat.S_ISREG(initial.st_mode):
            raise GateConfigError(f'bundle artifact must be a regular file, not a link: {path.name}')
        flags = os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_BINARY', 0)
        fd = _open_regular_file(str(path), flags)
        with os.fdopen(fd, 'rb', buffering=0) as fh:
            before = os.fstat(fh.fileno())
            data = _read_json_source(fh, str(path), 'bundle artifact')
            after = os.fstat(fh.fileno())
        signature = _signature(initial)
        if any(_signature(info) != signature for info in (before, after, path.lstat())):
            raise GateConfigError(f'bundle artifact changed while being read: {path.name}')
        return data, signature
    except (OSError, ValueError) as exc:
        raise GateConfigError(f'bundle artifact could not be read: {path.name}') from exc


def _no_lock(directory: Path) -> None:
    if os.path.lexists(directory / LOCK_NAME):
        raise GateConfigError('bundle has a publication lock; active or interrupted writes must be resolved first')


def _agree(actual: object, expected: object, label: str) -> None:
    # Canonical equality deliberately distinguishes JSON booleans and numbers.
    if _canonical_hash(actual, label) != _canonical_hash(expected, label):
        raise GateConfigError(f'{label} disagrees with the report')


def _check_report_and_manifest(report: dict, manifest: dict) -> str:
    for label, obj in (('report', report), ('manifest', manifest)):
        if obj.get('schema_version') != REPORT_SCHEMA_VERSION:
            raise GateConfigError(f'{label} has unsupported schema_version')
    tool = _object(report.get('tool'), 'report tool')
    if tool.get('name') != TOOL_NAME or not isinstance(tool.get('version'), str) or not tool['version']:
        raise GateConfigError('report tool identity is unsupported')
    _agree(manifest.get('tool'), tool, 'manifest tool')
    gate = _object(report.get('gate'), 'report gate')
    verdict = gate.get('verdict')
    if verdict not in ('pass', 'fail'):
        raise GateConfigError('report gate verdict must be pass or fail')
    rules = report.get('rules')
    if not isinstance(rules, list) or not rules:
        raise GateConfigError('report rules must be a non-empty list')
    states = []
    for rule in rules:
        state = _object(rule, 'report rule').get('verdict')
        if state not in ('pass', 'fail', 'warn', 'skipped'):
            raise GateConfigError('report rule has an invalid verdict')
        states.append(state)
    for name, count in (('n_rules', len(states)), ('n_failed', states.count('fail')),
                        ('n_warned', states.count('warn'))):
        if type(gate.get(name)) is not int or gate[name] != count:
            raise GateConfigError(f'report gate {name} disagrees with its rules')
    if verdict != ('fail' if 'fail' in states else 'pass'):
        raise GateConfigError('report gate verdict disagrees with its rules')
    _agree(manifest.get('gate_verdict'), verdict, 'manifest gate verdict')
    result_hash = _digest(report.get('result_hash'), 'report result hash')
    core = {key: value for key, value in report.items() if key != 'result_hash'}
    if _canonical_hash(core, 'report') != result_hash:
        raise GateConfigError('report result hash does not match its content')
    _agree(manifest.get('result_hash'), result_hash, 'manifest result hash')
    inputs = _object(report.get('inputs'), 'report inputs')
    manifest_inputs = _object(manifest.get('inputs'), 'manifest inputs')
    for role in ('dataset', 'baseline_config', 'candidate_config', 'scorer_config',
                 'thresholds', 'pricing_table'):
        report_input = _object(inputs.get(role), f'report {role}')
        manifest_input = _object(manifest_inputs.get(role), f'manifest {role}')
        if 'sha256' not in report_input or 'sha256' not in manifest_input:
            raise GateConfigError(f'{role} requires an explicit sha256 field')
        digest = report_input['sha256']
        if role != 'pricing_table' or digest is not None:
            _digest(digest, f'report {role} hash')
        _agree(manifest_input.get('sha256'), digest, f'manifest {role} hash')
        for key in ('name', 'version'):
            if key in manifest_input and key in report_input:
                _agree(manifest_input[key], report_input[key], f'manifest {role} {key}')
    runs = _object(report.get('runs'), 'report runs')
    providers = _object(manifest.get('providers'), 'manifest providers')
    for role in ('baseline', 'candidate'):
        run = _object(runs.get(role), f'report {role} run')
        provider = _object(run.get('provider'), f'report {role} provider')
        _agree(providers.get(role), provider, f'manifest {role} provider')
    _object(report.get('metrics'), 'report metrics')
    if not isinstance(report.get('items'), list):
        raise GateConfigError('report items must be a list')
    return result_hash


def verify_bundle(
    directory: str | os.PathLike[str], *, expected_result_hash: str | None = None,
    expected_bundle_hash: str | None = None, max_input_bytes: int = DEFAULT_MAX_BYTES,
) -> dict:
    """Read four fixed artifact names; return integrity evidence, not a new verdict."""
    if expected_result_hash is not None:
        _digest(expected_result_hash, 'expected result hash')
    if expected_bundle_hash is not None:
        _digest(expected_bundle_hash, 'expected bundle hash')
    directory = Path(directory)
    _no_lock(directory)
    snapshots = {}
    with input_byte_limit(max_input_bytes):
        for name in (*REPORT_FILES, 'manifest.json'):
            snapshots[name] = _read_artifact(directory / name)
    report = _decode_object(snapshots['report.json'][0], 'report.json')
    manifest = _decode_object(snapshots['manifest.json'][0], 'manifest.json')
    result_hash = _check_report_and_manifest(report, manifest)
    receipt = _object(manifest.get('bundle_integrity'), 'bundle integrity receipt')
    if set(receipt) != {'schema_version', 'result_hash', 'manifest_sha256', 'files', 'bundle_hash'}:
        raise GateConfigError('bundle integrity receipt has missing or unknown fields')
    if receipt['schema_version'] != BUNDLE_SCHEMA:
        raise GateConfigError('bundle integrity receipt has unsupported schema_version')
    _agree(receipt['result_hash'], result_hash, 'bundle receipt result hash')
    manifest_core = {key: value for key, value in manifest.items() if key != 'bundle_integrity'}
    if _digest(receipt['manifest_sha256'], 'manifest digest') != _canonical_hash(manifest_core, 'manifest'):
        raise GateConfigError('manifest digest does not match its content')
    entries = _object(receipt['files'], 'bundle receipt files')
    if set(entries) != set(REPORT_FILES):
        raise GateConfigError('bundle integrity receipt must name exactly the three report artifacts')
    for name in REPORT_FILES:
        entry = _object(entries[name], f'{name} receipt')
        if set(entry) != {'sha256', 'size_bytes'} or type(entry.get('size_bytes')) is not int:
            raise GateConfigError(f'{name} receipt requires a digest and integer size_bytes')
        data = snapshots[name][0]
        digest = _digest(entry['sha256'], f'{name} digest')
        if len(data) != entry['size_bytes'] or 'sha256:' + hashlib.sha256(data).hexdigest() != digest:
            raise GateConfigError(f'bundle artifact digest or size mismatch: {name}')
    bundle_hash = _digest(receipt['bundle_hash'], 'bundle hash')
    receipt_core = {key: value for key, value in receipt.items() if key != 'bundle_hash'}
    if content_hash(receipt_core) != bundle_hash:
        raise GateConfigError('bundle hash does not match its receipt')
    if expected_result_hash is not None and result_hash != expected_result_hash:
        raise GateConfigError('expected result hash does not match the bundle')
    if expected_bundle_hash is not None and bundle_hash != expected_bundle_hash:
        raise GateConfigError('expected bundle hash does not match the bundle')
    _no_lock(directory)
    try:
        for name, (_, signature) in snapshots.items():
            if _signature((directory / name).lstat()) != signature:
                raise GateConfigError(f'bundle artifact changed during verification: {name}')
    except OSError as exc:
        raise GateConfigError('bundle changed during verification') from exc
    return {
        'schema_version': 'lrg-bundle-verification/1',
        'integrity': 'verified',
        'gate_verdict': report['gate']['verdict'],
        'result_hash': result_hash,
        'bundle_hash': bundle_hash,
        'files_verified': [*REPORT_FILES, 'manifest.json'],
        'external_pins': {'result_hash': expected_result_hash is not None,
                          'bundle_hash': expected_bundle_hash is not None},
        'input_sources_verified': False,
        'policy_recomputed': False,
        'authenticity_verified': False,
        'limitations': ['Content consistency is not producer authenticity or proof of model execution.',
                        'Input sources, scoring, policy correctness and freshness were not independently verified.'],
    }
