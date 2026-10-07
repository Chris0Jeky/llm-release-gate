"""Offline integrity checks must not turn matching bytes into release authority."""

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil

import pytest

from conftest import gate_argv
from llm_release_gate.cli import main
from llm_release_gate.errors import GateConfigError
from llm_release_gate.hashing import content_hash

FILES = ('report.json', 'report.md', 'report.html')
ALL_FILES = (*FILES, 'manifest.json')


def module():
    assert importlib.util.find_spec('llm_release_gate.bundles') is not None
    from llm_release_gate import bundles
    return bundles


def prepared(mini_gate, *, red=False):
    paths = mini_gate(thresholds={'rules': [{'metric': 'quality.pass_rate', 'min_value': 1.1}]} if red else None)
    assert main(gate_argv(paths)) == (1 if red else 0)
    out = Path(paths['out'])
    manifest = json.loads((out / 'manifest.json').read_text())
    assert 'bundle_integrity' in manifest, 'gate must publish an integrity receipt'
    return paths, out, manifest


def reseal(out, manifest):
    """Model an adversary able to rewrite ALL unpinned artifact declarations."""
    manifest.pop('bundle_integrity', None)
    report = json.loads((out / 'report.json').read_text())
    receipt = {
        'schema_version': 'lrg-report-bundle/1',
        'result_hash': report['result_hash'],
        'manifest_sha256': content_hash(manifest),
        'files': {name: {'sha256': 'sha256:' + hashlib.sha256((out / name).read_bytes()).hexdigest(),
                        'size_bytes': (out / name).stat().st_size} for name in FILES},
    }
    receipt['bundle_hash'] = content_hash(receipt)
    manifest['bundle_integrity'] = receipt
    (out / 'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')


def write_changed_report(out, report):
    report.pop('result_hash')
    report['result_hash'] = content_hash(report)
    (out / 'report.json').write_text(json.dumps(report), encoding='utf-8')


def test_manifest_receipt_pins_artifacts_and_volatile_manifest(mini_gate):
    _, out, manifest = prepared(mini_gate)
    receipt = manifest.pop('bundle_integrity')
    assert receipt['manifest_sha256'] == content_hash(manifest)
    assert receipt['result_hash'] == manifest['result_hash']
    assert set(receipt['files']) == set(FILES)
    for name in FILES:
        data = (out / name).read_bytes()
        assert receipt['files'][name] == {
            'sha256': 'sha256:' + hashlib.sha256(data).hexdigest(), 'size_bytes': len(data),
        }
    bundle_hash = receipt.pop('bundle_hash')
    assert bundle_hash == content_hash(receipt)


@pytest.mark.parametrize('red', [False, True])
def test_verify_distinguishes_intact_bundle_from_passing_gate(mini_gate, capsys, red):
    _, out, manifest = prepared(mini_gate, red=red)
    capsys.readouterr()
    argv = ['verify', '--bundle', str(out), '--json']
    assert main(argv) == 0
    proof = json.loads(capsys.readouterr().out)
    assert proof['integrity'] == 'verified'
    assert proof['gate_verdict'] == ('fail' if red else 'pass')
    assert proof['bundle_hash'] == manifest['bundle_integrity']['bundle_hash']
    assert proof['input_sources_verified'] is False
    assert proof['policy_recomputed'] is False
    assert proof['authenticity_verified'] is False
    assert proof['external_pins'] == {'result_hash': False, 'bundle_hash': False}
    assert main(argv + ['--require-pass']) == (1 if red else 0)


def test_both_external_pins_are_checked_and_reported(mini_gate):
    _, out, manifest = prepared(mini_gate)
    proof = module().verify_bundle(out, expected_result_hash=manifest['result_hash'],
                                   expected_bundle_hash=manifest['bundle_integrity']['bundle_hash'])
    assert proof['external_pins'] == {'result_hash': True, 'bundle_hash': True}


@pytest.mark.parametrize('name', ALL_FILES)
@pytest.mark.parametrize('mutation', ['missing', 'append', 'truncated'])
def test_missing_modified_or_partial_artifact_refused(mini_gate, capsys, name, mutation):
    _, out, _ = prepared(mini_gate)
    path = out / name
    if mutation == 'missing':
        path.unlink()
    elif mutation == 'append':
        # Whitespace after manifest JSON is semantically immaterial; change its metadata instead.
        if name == 'manifest.json':
            data = json.loads(path.read_text())
            data['created_at'] = 'different capture'
            path.write_text(json.dumps(data))
        else:
            path.write_bytes(path.read_bytes() + b' ')
    else:
        path.write_bytes(path.read_bytes()[:12])
    assert main(['verify', '--bundle', str(out)]) == 2
    assert 'Traceback' not in capsys.readouterr().err


@pytest.mark.parametrize('name', ALL_FILES)
def test_final_symlinks_are_not_followed(mini_gate, name):
    paths, out, _ = prepared(mini_gate)
    external = paths['tmp'] / ('external-' + name)
    (out / name).rename(external)
    try:
        (out / name).symlink_to(external)
    except OSError:
        pytest.skip('symlinks unavailable')
    with pytest.raises(GateConfigError, match='regular file'):
        module().verify_bundle(out)


def test_locked_bundle_cannot_be_verified_or_unlock_itself(mini_gate):
    _, out, _ = prepared(mini_gate)
    lock = out / '.llm-release-gate.lock'
    lock.write_text('writer or crash residue')
    with pytest.raises(GateConfigError, match='lock'):
        module().verify_bundle(out)
    assert lock.read_text() == 'writer or crash residue'


def test_relocated_bundle_needs_no_input_files_or_execution(mini_gate, monkeypatch):
    paths, out, manifest = prepared(mini_gate)
    relocated = paths['tmp'] / 'moved'
    shutil.copytree(out, relocated)
    for key in ('dataset', 'candidate', 'baseline', 'scorers', 'thresholds', 'pricing'):
        Path(paths[key]).unlink()
    shutil.rmtree(paths['tmp'] / 'fixtures')
    from llm_release_gate.providers.fake import FakeProvider
    def forbidden(*args, **kwargs):
        pytest.fail('verification constructed a provider')
    monkeypatch.setattr(FakeProvider, '__init__', forbidden)
    assert module().verify_bundle(relocated, expected_bundle_hash=manifest['bundle_integrity']['bundle_hash'])['integrity'] == 'verified'
    assert set(p.name for p in relocated.iterdir()) == set(ALL_FILES)


@pytest.mark.parametrize('document', ['report.json', 'manifest.json'])
@pytest.mark.parametrize('duplicate', ['"schema_version":"1",', '"schema_versio\\u006e":"1",'])
def test_duplicate_json_keys_are_rejected(mini_gate, document, duplicate):
    _, out, _ = prepared(mini_gate)
    path = out / document
    raw = path.read_text()
    path.write_text('{' + duplicate + raw[1:])
    with pytest.raises(GateConfigError, match='duplicate'):
        module().verify_bundle(out)


@pytest.mark.parametrize('token', ['NaN', 'Infinity', '-Infinity', '1e999'])
def test_nonfinite_manifest_json_is_refused_without_echoing_values(mini_gate, token):
    _, out, _ = prepared(mini_gate)
    path = out / 'manifest.json'
    raw = path.read_text()
    path.write_text('{"SECRET":' + token + ',' + raw[1:])
    with pytest.raises(GateConfigError) as exc:
        module().verify_bundle(out)
    assert 'SECRET' not in str(exc.value)


@pytest.mark.parametrize('field,value', [('schema_version', '2'), ('files', {}),
    ('bundle_hash', 'sha256:' + '0'*64), ('manifest_sha256', None), ('result_hash', True)])
def test_bad_receipt_contract_is_refused(mini_gate, field, value):
    _, out, manifest = prepared(mini_gate)
    manifest['bundle_integrity'][field] = value
    (out / 'manifest.json').write_text(json.dumps(manifest))
    with pytest.raises(GateConfigError):
        module().verify_bundle(out)


def test_boolean_size_cannot_equal_integer_length(mini_gate):
    _, out, manifest = prepared(mini_gate)
    receipt = manifest['bundle_integrity']
    receipt['files']['report.json']['size_bytes'] = True
    receipt.pop('bundle_hash')
    receipt['bundle_hash'] = content_hash(receipt)
    (out / 'manifest.json').write_text(json.dumps(manifest))
    with pytest.raises(GateConfigError):
        module().verify_bundle(out)


@pytest.mark.parametrize('field', ['gate_verdict', 'result_hash', 'tool', 'providers', 'inputs'])
def test_resealed_manifest_must_still_agree_with_report(mini_gate, field):
    _, out, manifest = prepared(mini_gate)
    if field == 'gate_verdict':
        manifest[field] = 'fail'
    elif field == 'result_hash':
        manifest[field] = 'sha256:' + '0'*64
    else:
        manifest[field] = {}
    reseal(out, manifest)
    with pytest.raises(GateConfigError):
        module().verify_bundle(out)


def test_trusted_pin_catches_fully_resealed_report_mutation(mini_gate):
    _, out, manifest = prepared(mini_gate)
    original = manifest['result_hash']
    report = json.loads((out / 'report.json').read_text())
    report['items'][0]['candidate']['text'] = 'forged answer'
    write_changed_report(out, report)
    manifest['result_hash'] = report['result_hash']
    reseal(out, manifest)
    # Unpinned consistency is not authenticity; a full rewrite can be self-consistent.
    assert module().verify_bundle(out)['integrity'] == 'verified'
    with pytest.raises(GateConfigError, match='expected result hash'):
        module().verify_bundle(out, expected_result_hash=original)


def test_bundle_pin_covers_manifest_metadata_not_only_report(mini_gate):
    _, out, manifest = prepared(mini_gate)
    original = manifest['bundle_integrity']['bundle_hash']
    manifest['created_at'] = 'tampered timestamp'
    reseal(out, manifest)
    with pytest.raises(GateConfigError, match='expected bundle hash'):
        module().verify_bundle(out, expected_bundle_hash=original)


def test_stored_paths_are_data_never_file_access_instructions(mini_gate, monkeypatch):
    _, out, manifest = prepared(mini_gate)
    manifest['report_files'] = {key: '/do-not-read-this' for key in manifest['report_files']}
    for value in manifest['inputs'].values():
        value['path'] = '/do-not-read-this'
    reseal(out, manifest)
    import builtins
    original_open = builtins.open
    def guarded_open(path, *args, **kwargs):
        assert str(path) != '/do-not-read-this'
        return original_open(path, *args, **kwargs)
    monkeypatch.setattr(builtins, 'open', guarded_open)
    assert module().verify_bundle(out)['integrity'] == 'verified'


@pytest.mark.parametrize('pin', ['', 'sha256:abc', 'SHA256:'+'a'*64, 'sha256:'+'A'*64, True, 5])
def test_invalid_external_pin_refused_before_reading(tmp_path, pin):
    with pytest.raises(GateConfigError, match='expected result hash'):
        module().verify_bundle(tmp_path / 'missing', expected_result_hash=pin)


def test_verification_size_cap_is_enforced(mini_gate):
    _, out, _ = prepared(mini_gate)
    with pytest.raises(GateConfigError, match='max input size'):
        module().verify_bundle(out, max_input_bytes=1)


def test_verification_has_no_github_output_side_effects(mini_gate, monkeypatch):
    paths, out, _ = prepared(mini_gate)
    sink = paths['tmp'] / 'github-output'
    sink.write_text('unchanged')
    monkeypatch.setenv('GITHUB_OUTPUT', str(sink))
    monkeypatch.setenv('GITHUB_STEP_SUMMARY', str(sink))
    assert main(['verify', '--bundle', str(out)]) == 0
    assert sink.read_text() == 'unchanged'


def test_legacy_manifest_is_explicitly_unsupported(mini_gate):
    _, out, manifest = prepared(mini_gate)
    manifest.pop('bundle_integrity')
    (out / 'manifest.json').write_text(json.dumps(manifest))
    with pytest.raises(GateConfigError, match='integrity receipt'):
        module().verify_bundle(out)


@pytest.mark.parametrize('side', ['report', 'manifest'])
def test_omitted_pricing_hash_is_not_equivalent_to_explicit_unknown(mini_gate, side):
    paths = mini_gate()
    args = gate_argv(paths)
    i = args.index('--pricing')
    del args[i:i + 2]
    assert main(args) == 0
    out = Path(paths['out'])
    manifest = json.loads((out / 'manifest.json').read_text())
    if side == 'report':
        report = json.loads((out / 'report.json').read_text())
        del report['inputs']['pricing_table']['sha256']
        write_changed_report(out, report)
        manifest['result_hash'] = report['result_hash']
    else:
        del manifest['inputs']['pricing_table']['sha256']
    reseal(out, manifest)
    with pytest.raises(GateConfigError, match='pricing_table.*sha256'):
        module().verify_bundle(out)


@pytest.mark.parametrize('field,value', [('verdict', 'unknown'), ('verdict', {}),
    ('n_rules', True), ('n_failed', -1), ('n_warned', 100)])
def test_resealed_header_inconsistency_is_refused(mini_gate, field, value):
    _, out, manifest = prepared(mini_gate)
    report = json.loads((out / 'report.json').read_text())
    report['gate'][field] = value
    write_changed_report(out, report)
    manifest['result_hash'] = report['result_hash']
    manifest['gate_verdict'] = report['gate']['verdict']
    reseal(out, manifest)
    with pytest.raises(GateConfigError, match='report gate'):
        module().verify_bundle(out)


def test_manifest_reformatting_preserves_canonical_bundle_pin(mini_gate):
    _, out, manifest = prepared(mini_gate)
    pin = manifest['bundle_integrity']['bundle_hash']
    (out / 'manifest.json').write_text(json.dumps(manifest, sort_keys=True, indent=4))
    assert module().verify_bundle(out, expected_bundle_hash=pin)['integrity'] == 'verified'


@pytest.mark.parametrize('change', ['artifact', 'lock'])
def test_changed_bundle_is_refused_at_final_snapshot_check(mini_gate, monkeypatch, change):
    _, out, _ = prepared(mini_gate)
    bundles = module()
    original = bundles._check_report_and_manifest
    def concurrent_writer(report, manifest):
        result = original(report, manifest)
        if change == 'artifact':
            path = out / 'report.md'
            path.write_bytes(path.read_bytes() + b'changed after read')
        else:
            (out / '.llm-release-gate.lock').write_text('writer')
        return result
    monkeypatch.setattr(bundles, '_check_report_and_manifest', concurrent_writer)
    with pytest.raises(GateConfigError, match='changed|lock'):
        bundles.verify_bundle(out)


def test_action_exports_bundle_pin_and_verifies_actual_outputs():
    root = Path(__file__).resolve().parents[1]
    action = (root / 'action.yml').read_text()
    workflow = (root / '.github/workflows/ci.yml').read_text()
    assert 'value: ${{ steps.gate.outputs.bundle-hash }}' in action
    assert 'EXPECTED_BUNDLE_HASH: ${{ steps.bound.outputs.bundle-hash }}' in workflow
    assert '--expected-bundle-hash "$EXPECTED_BUNDLE_HASH"' in workflow
