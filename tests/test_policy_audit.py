"""A consumer applies its own policy to one verified stored-aggregate snapshot."""

import hashlib
import importlib.util
import json
from pathlib import Path
import shutil

import pytest

from conftest import gate_argv
from llm_release_gate import bundles, cli
from llm_release_gate.errors import GateConfigError
from llm_release_gate.hashing import content_hash


def auditor():
    assert importlib.util.find_spec('llm_release_gate.audit') is not None
    from llm_release_gate import audit
    return audit


def setup(mini_gate, *, original_red=False, rules=None):
    paths = mini_gate(thresholds={'rules': [{'metric': 'quality.pass_rate', 'min_value': 1.1}]}
                      if original_red else None)
    assert cli.main(gate_argv(paths)) == (1 if original_red else 0)
    out = Path(paths['out'])
    policy = paths['tmp'] / 'consumer-policy.json'
    policy.write_text(json.dumps({'rules': rules or [{'metric': 'quality.pass_rate', 'min_value': 1}]}))
    manifest = json.loads((out / 'manifest.json').read_text())
    return paths, out, policy, manifest


def reseal(out, change):
    report = json.loads((out / 'report.json').read_text())
    change(report)
    report.pop('result_hash')
    report['result_hash'] = content_hash(report)
    (out / 'report.json').write_text(json.dumps(report))
    manifest = json.loads((out / 'manifest.json').read_text())
    manifest.pop('bundle_integrity')
    manifest['result_hash'] = report['result_hash']
    manifest['bundle_integrity'] = bundles.build_bundle_receipt(manifest,
        {name: (out / name).read_bytes() for name in bundles.REPORT_FILES})
    (out / 'manifest.json').write_text(json.dumps(manifest))


@pytest.mark.parametrize('original_red,minimum,new_verdict', [(False, 1, 'pass'),
    (False, 1.1, 'fail'), (True, 1, 'pass'), (True, 1.1, 'fail')])
def test_consumer_policy_is_distinct_from_original_verdict(mini_gate, original_red, minimum, new_verdict):
    paths, out, policy, manifest = setup(mini_gate, original_red=original_red,
        rules=[{'metric': 'quality.pass_rate', 'min_value': minimum}])
    before = {p.name: p.read_bytes() for p in out.iterdir()}
    proof = auditor().audit_bundle(out, policy)
    assert proof['schema_version'] == 'lrg-policy-audit/1'
    assert proof['recorded_gate_verdict'] == ('fail' if original_red else 'pass')
    assert proof['policy_verdict'] == new_verdict
    assert proof['result_hash'] == manifest['result_hash']
    assert proof['bundle_hash'] == manifest['bundle_integrity']['bundle_hash']
    assert proof['policy_hash'] == 'sha256:' + hashlib.sha256(policy.read_bytes()).hexdigest()
    assert proof['basis'] == 'stored_aggregates'
    for key in ('source_inputs_verified', 'scores_recomputed', 'original_policy_recomputed', 'authenticity_verified'):
        assert proof[key] is False
    digest = proof.pop('audit_hash')
    assert digest == content_hash(proof)
    assert {p.name: p.read_bytes() for p in out.iterdir()} == before
    assert any(rule['implicit'] and rule['metric'] == 'errors.error_rate' for rule in proof['rules'])
    assert 'The sky is blue' not in json.dumps(proof)


@pytest.mark.parametrize('minimum,expected', [(1, 0), (1.1, 1)])
def test_cli_emits_json_and_new_policy_exit_without_github_side_effects(mini_gate, capsys, monkeypatch, minimum, expected):
    _, out, policy, _ = setup(mini_gate, rules=[{'metric': 'quality.pass_rate', 'min_value': minimum}])
    auditor()
    capsys.readouterr()
    sink = out.parent / 'sink'
    sink.write_text('unchanged')
    for name in ('GITHUB_OUTPUT', 'GITHUB_STEP_SUMMARY'):
        monkeypatch.setenv(name, str(sink))
    assert cli.main(['audit', '--bundle', str(out), '--thresholds', str(policy), '--json']) == expected
    proof = json.loads(capsys.readouterr().out)
    assert proof['policy_verdict'] == ('pass' if expected == 0 else 'fail')
    assert sink.read_text() == 'unchanged'


@pytest.mark.parametrize('name', ['expected_result_hash', 'expected_bundle_hash', 'expected_policy_hash'])
def test_external_pin_mismatch_is_refused(mini_gate, name):
    _, out, policy, _ = setup(mini_gate)
    with pytest.raises(GateConfigError, match='expected'):
        auditor().audit_bundle(out, policy, **{name: 'sha256:' + '0'*64})


def test_all_pins_are_checked_and_recorded(mini_gate):
    _, out, policy, manifest = setup(mini_gate)
    proof = auditor().audit_bundle(out, policy,
        expected_result_hash=manifest['result_hash'],
        expected_bundle_hash=manifest['bundle_integrity']['bundle_hash'],
        expected_policy_hash='sha256:' + hashlib.sha256(policy.read_bytes()).hexdigest())
    assert proof['external_pins'] == {'result_hash': True, 'bundle_hash': True, 'policy_hash': True}


@pytest.mark.parametrize('raw', ['{"rules":[],"rules":[]}', '{"rules":[{"metric":"q","min_value":NaN}]}',
    '{"rules":[]}', '{"rules":[{"metric":"quality.pass_rate","min_value":true}]}',
    '{"rules":[{"metric":"quality.pass_rate","typo":0}]}', '[]'])
def test_ambiguous_or_malformed_policy_is_refused(mini_gate, raw):
    _, out, policy, _ = setup(mini_gate)
    policy.write_text(raw)
    with pytest.raises(GateConfigError):
        auditor().audit_bundle(out, policy)


def test_unknown_metric_fails_not_silently_skipped(mini_gate):
    _, out, policy, _ = setup(mini_gate, rules=[{'metric': 'unknown', 'min_value': 1, 'on_unavailable': 'skip'}])
    with pytest.raises(GateConfigError, match='unknown'):
        auditor().audit_bundle(out, policy)


@pytest.mark.parametrize('field,value', [('value', True), ('available', 'true'), ('direction', 'anything'),
    ('numerator', 0), ('denominator', True), ('n', -1)])
def test_resealed_malformed_metrics_are_not_auditable(mini_gate, field, value):
    _, out, policy, _ = setup(mini_gate)
    def change(report):
        for record in (report['metrics']['quality.pass_rate']['candidate'],
                       report['runs']['candidate']['aggregates']['quality.pass_rate']):
            record[field] = value
    reseal(out, change)
    assert bundles.verify_bundle(out)['integrity'] == 'verified'  # integrity is deliberately weaker
    with pytest.raises(GateConfigError):
        auditor().audit_bundle(out, policy)


def test_conflicting_aggregate_copies_are_rejected(mini_gate):
    _, out, policy, _ = setup(mini_gate)
    reseal(out, lambda report: report['runs']['candidate']['aggregates']['quality.pass_rate'].update(value=0))
    with pytest.raises(GateConfigError, match='aggregate'):
        auditor().audit_bundle(out, policy)


def test_audit_is_relocation_stable_and_needs_no_original_sources(mini_gate, monkeypatch):
    paths, out, policy, _ = setup(mini_gate)
    mod = auditor()
    original = mod.audit_bundle(out, policy)
    moved = paths['tmp'] / 'moved'
    shutil.copytree(out, moved)
    new_policy = moved / 'explicit-policy.json'
    new_policy.write_bytes(policy.read_bytes())
    for role in ('dataset', 'candidate', 'baseline', 'scorers', 'thresholds', 'pricing'):
        Path(paths[role]).unlink()
    shutil.rmtree(paths['tmp'] / 'fixtures')
    from llm_release_gate.providers.fake import FakeProvider
    monkeypatch.setattr(FakeProvider, '__init__', lambda *a, **k: pytest.fail('constructed provider'))
    assert mod.audit_bundle(moved, new_policy) == original


def test_audit_uses_verified_snapshot_without_reopening_report(mini_gate, monkeypatch):
    _, out, policy, _ = setup(mini_gate, rules=[{'metric': 'quality.pass_rate', 'min_value': 1.1}])
    mod = auditor()
    original = mod._verified_bundle_snapshot
    def mutate_after_snapshot(*args, **kwargs):
        verified = original(*args, **kwargs)
        (out / 'report.json').write_text('not JSON; must not reopen')
        return verified
    monkeypatch.setattr(mod, '_verified_bundle_snapshot', mutate_after_snapshot)
    assert mod.audit_bundle(out, policy)['policy_verdict'] == 'fail'


@pytest.mark.parametrize('target', ['policy', 'artifact'])
def test_audit_limits_all_sources(mini_gate, target):
    _, out, policy, _ = setup(mini_gate)
    path = policy if target == 'policy' else out / 'report.md'
    path.write_bytes(path.read_bytes() + b' ' * 100001)
    with pytest.raises(GateConfigError, match='max input size'):
        auditor().audit_bundle(out, policy, max_input_bytes=100000)


@pytest.mark.parametrize('behavior,expected', [('skip', 'pass'), ('warn', 'pass'), ('fail', 'fail')])
def test_unavailable_policy_remains_explicit(mini_gate, behavior, expected):
    _, out, policy, _ = setup(mini_gate, rules=[{'metric': 'cost.total_usd', 'max_value': 1,
                                              'on_unavailable': behavior}])
    def missing(report):
        from llm_release_gate.metrics import unavailable_metric, LOWER
        metric = unavailable_metric('usd', LOWER, 'unknown')
        report['metrics']['cost.total_usd']['candidate'] = metric
        report['runs']['candidate']['aggregates']['cost.total_usd'] = metric
    reseal(out, missing)
    assert auditor().audit_bundle(out, policy)['policy_verdict'] == expected


@pytest.mark.parametrize('scenario,expected', [('rag-support-bot', 'pass'), ('extraction-api', 'pass'),
    ('assistant-cheap-regression', 'fail'), ('request-bound-replay', 'pass')])
def test_all_public_examples_reproduce_policy_verdict_from_stored_aggregates(tmp_path, scenario, expected):
    root = Path(__file__).resolve().parents[1]
    example = root / 'examples' / scenario
    out = tmp_path / 'bundle'
    args = ['gate', '--out', str(out)]
    for name in ('dataset', 'baseline', 'candidate', 'scorers', 'thresholds'):
        args += ['--' + name, str(example / (name + '.json'))]
    if scenario != 'request-bound-replay':
        args += ['--pricing', str(root / 'examples/pricing.json')]
    assert cli.main(args) == (0 if expected == 'pass' else 1)
    proof = auditor().audit_bundle(out, example / 'thresholds.json')
    assert proof['policy_verdict'] == proof['recorded_gate_verdict'] == expected


def test_policy_symlink_is_refused(mini_gate):
    _, out, policy, _ = setup(mini_gate)
    moved = policy.with_name('moved-policy.json')
    policy.rename(moved)
    try:
        policy.symlink_to(moved)
    except OSError:
        pytest.skip('symlinks unavailable')
    with pytest.raises(GateConfigError, match='regular file'):
        auditor().audit_bundle(out, policy)


def test_duplicate_valid_rules_key_is_rejected_not_last_wins(mini_gate):
    _, out, policy, _ = setup(mini_gate)
    strict = '{"metric":"quality.pass_rate","min_value":1.1}'
    relaxed = '{"metric":"quality.pass_rate","min_value":0}'
    policy.write_text('{"rules":[' + strict + '],"rules":[' + relaxed + ']}')
    with pytest.raises(GateConfigError, match='duplicate'):
        auditor().audit_bundle(out, policy)


def test_action_qualifies_pinned_consumer_policy_audit():
    workflow = (Path(__file__).resolve().parents[1] / '.github/workflows/ci.yml').read_text()
    assert 'Audit the pinned bundle under an independent consumer policy' in workflow
    assert 'llm_release_gate audit --bundle out/action-bound' in workflow
    assert '--expected-policy-hash "$EXPECTED_POLICY_HASH"' in workflow
