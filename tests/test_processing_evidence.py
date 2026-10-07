"""Post-response failures must not erase measurements or understate totals."""

import json
from pathlib import Path

import pytest

from conftest import GOOD_RESPONSE, gate_argv
from llm_release_gate import cli, runner
from llm_release_gate.adapters.grounded import RagAdapter
from llm_release_gate.errors import GateConfigError, ProviderError
from llm_release_gate.scorers.quality import KeywordQualityScorer


def failing_gate(mini_gate, monkeypatch, stage, *, error=RuntimeError, all_items=False,
                 on_unavailable='fail'):
    responses = {key: dict(value) for key, value in GOOD_RESPONSE.items()}
    responses['r2']['prompt_tokens'] = 1_000_000
    for key, response in responses.items():
        response['text'] += ' candidate-only'
    paths = mini_gate(candidate_responses=responses, thresholds={'rules': [
        {'metric': 'errors.error_rate', 'max_value': 1},
        {'metric': 'cost.total_usd', 'max_value': 0.1, 'on_unavailable': on_unavailable},
    ]})
    if stage == 'parse':
        original = RagAdapter.parse
        def fail(self, text, item):
            if 'candidate-only' in text and (all_items or item.id == 'r2'):
                raise error('processing probe')
            return original(self, text, item)
        monkeypatch.setattr(RagAdapter, 'parse', fail)
    elif stage == 'score':
        original = KeywordQualityScorer.score_item
        def fail(self, item, output):
            if 'candidate-only' in output.text and (all_items or item.id == 'r2'):
                raise error('processing probe')
            return original(self, item, output)
        monkeypatch.setattr(KeywordQualityScorer, 'score_item', fail)
    elif stage == 'pricing':
        original = runner.item_cost_usd
        def fail(result, pricing):
            if result.model == 'm-cand' and (all_items or result.prompt_tokens == 1_000_000):
                raise error('processing probe')
            return original(result, pricing)
        monkeypatch.setattr(runner, 'item_cost_usd', fail)
    return paths


@pytest.mark.parametrize('stage', ['parse', 'score', 'pricing'])
def test_processing_failure_retains_measurements_and_cannot_hide_cost(mini_gate, monkeypatch, stage):
    paths = failing_gate(mini_gate, monkeypatch, stage)
    assert cli.main(gate_argv(paths)) == 1  # previously passes the cost ceiling
    report = json.loads((Path(paths['out']) / 'report.json').read_text())
    failed = report['items'][1]['candidate']
    assert failed['status'] == 'error' and failed['error_stage'] == stage
    assert failed['prompt_tokens'] == 1_000_000
    assert failed['completion_tokens'] == 22
    assert failed['latency_ms'] == 520
    assert failed['text'].endswith('candidate-only')
    assert failed['scores'] == {}  # no partial successful score vector
    if stage == 'pricing':
        assert failed['cost_usd'] is None
        assert 'pricing' in failed['cost_note']
    else:
        assert failed['cost_usd'] == 1.000044
    for key in ('tokens.total', 'cost.total_usd'):
        metric = report['metrics'][key]['candidate']
        assert metric['available'] is False
        assert metric['value'] is None
        assert 'post-response' in metric['note']
    assert report['runs']['candidate']['n_ok'] == 2
    assert report['runs']['candidate']['n_processing_errors'] == 1
    rule = next(rule for rule in report['rules'] if rule['metric'] == 'cost.total_usd')
    assert rule['checks'][0]['status'] == 'unavailable'
    assert report['metrics']['errors.error_rate']['candidate']['value'] == 1/3


@pytest.mark.parametrize('stage', ['parse', 'score', 'pricing'])
def test_failure_attribution_survives_all_renderers(mini_gate, monkeypatch, stage):
    paths = failing_gate(mini_gate, monkeypatch, stage)
    cli.main(gate_argv(paths))
    for extension in ('json', 'md', 'html'):
        text = (Path(paths['out']) / ('report.' + extension)).read_text()
        assert 'item-processing errors' in text
        assert 'candidate run had 1/3 provider errors' not in text
    # A correctly serialized error bundle is still internally verifiable.
    assert cli.main(['verify', '--bundle', paths['out'], '--require-pass']) == 1


@pytest.mark.parametrize('stage', ['parse', 'score'])
def test_provider_error_from_processing_keeps_correct_stage(mini_gate, monkeypatch, stage):
    paths = failing_gate(mini_gate, monkeypatch, stage, error=ProviderError)
    assert cli.main(gate_argv(paths)) == 1
    failed = json.loads((Path(paths['out']) / 'report.json').read_text())['items'][1]['candidate']
    assert failed['error_stage'] == stage
    assert failed['prompt_tokens'] == 1_000_000


@pytest.mark.parametrize('stage', ['parse', 'score', 'pricing'])
def test_configuration_failure_still_aborts_without_new_evidence(mini_gate, monkeypatch, stage):
    paths = failing_gate(mini_gate, monkeypatch, stage, error=GateConfigError)
    assert cli.main(gate_argv(paths)) == 2
    assert not Path(paths['out']).exists()


def test_all_post_response_errors_retain_records_not_fabricated_aggregates(mini_gate, monkeypatch):
    paths = failing_gate(mini_gate, monkeypatch, 'parse', all_items=True)
    assert cli.main(gate_argv(paths)) == 1
    report = json.loads((Path(paths['out']) / 'report.json').read_text())
    assert all(item['candidate']['prompt_tokens'] is not None for item in report['items'])
    assert report['runs']['candidate']['n_processing_errors'] == 3
    assert report['metrics']['cost.total_usd']['candidate']['available'] is False


def test_pre_request_error_does_not_inherit_previous_response(mini_gate, monkeypatch):
    paths = mini_gate()
    original = RagAdapter.build_request
    def fail(self, item, config):
        if item.id == 'r2' and config.model == 'm-cand':
            raise RuntimeError('before any call')
        return original(self, item, config)
    monkeypatch.setattr(RagAdapter, 'build_request', fail)
    assert cli.main(gate_argv(paths)) == 1
    report = json.loads((Path(paths['out']) / 'report.json').read_text())
    failed = report['items'][1]['candidate']
    assert failed['error_stage'] == 'request'
    assert failed['prompt_tokens'] is None and failed['text'] is None
    # No returned response was dropped; answered-item totals retain their contract.
    assert report['metrics']['tokens.total']['candidate']['value'] == 225


@pytest.mark.parametrize('policy,expected', [('skip', 0), ('warn', 0), ('fail', 1)])
def test_unavailable_policy_is_not_silently_overridden(mini_gate, monkeypatch, policy, expected):
    paths = failing_gate(mini_gate, monkeypatch, 'parse', on_unavailable=policy)
    assert cli.main(gate_argv(paths)) == expected
    report = json.loads((Path(paths['out']) / 'report.json').read_text())
    assert report['metrics']['cost.total_usd']['candidate']['available'] is False


def test_diagnostic_error_output_retains_consumption(mini_gate, monkeypatch):
    paths = failing_gate(mini_gate, monkeypatch, 'parse')
    argv = ['run', '--dataset', paths['dataset'], '--config', paths['candidate'],
            '--scorers', paths['scorers'], '--pricing', paths['pricing'], '--out', paths['out']]
    assert cli.main(argv) == 0
    content = (Path(paths['out']) / 'run.json').read_bytes()
    assert json.loads(content)['items'][1]['prompt_tokens'] == 1_000_000
    assert cli.main(argv + ['--fail-on-errors']) == 2
    assert (Path(paths['out']) / 'run.json').read_bytes() == content


def test_huge_usage_cost_overflow_cannot_hide_behind_tolerated_errors(mini_gate):
    """Reach the bug through built-in replay, without a custom provider or mock."""
    responses = {key: dict(value) for key, value in GOOD_RESPONSE.items()}
    responses['r2']['prompt_tokens'] = 10**400
    paths = mini_gate(candidate_responses=responses, thresholds={'rules': [
        {'metric': 'errors.error_rate', 'max_value': 1},
        {'metric': 'cost.total_usd', 'max_value': 0.1},
    ]})
    assert cli.main(gate_argv(paths)) == 1
    report = json.loads((Path(paths['out']) / 'report.json').read_text())
    failed = report['items'][1]['candidate']
    assert failed['error_stage'] == 'pricing'
    assert failed['prompt_tokens'] == 10**400
    assert report['metrics']['cost.total_usd']['candidate']['available'] is False


def test_ordinary_provider_failure_keeps_existing_identity_and_sample_scope(mini_gate):
    responses = {key: dict(value) for key, value in GOOD_RESPONSE.items()}
    responses['r2'] = {'error': 'simulated outage'}
    paths = mini_gate(candidate_responses=responses)
    assert cli.main(gate_argv(paths)) == 1
    report = json.loads((Path(paths['out']) / 'report.json').read_text())
    assert 'n_processing_errors' not in report['runs']['candidate']
    assert 'error_stage' not in report['items'][1]['candidate']
    assert report['metrics']['tokens.total']['candidate']['value'] == 225
    assert any('1/3 provider errors' in notice for notice in report['gate']['notices'])
