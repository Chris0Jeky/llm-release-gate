"""Writer, pagination and concurrent-run controls, without network access."""

import json
from pathlib import Path
import subprocess
from types import SimpleNamespace

import pytest

from pr_comment_fakes import FakeGithub, invocation, load_reporter


@pytest.mark.parametrize('existing', [False, True])
def test_spoofed_marker_and_paginated_comments_never_select_another_writer(tmp_path, existing):
    reporter, api = load_reporter(), FakeGithub()
    spoof = api.add(reporter.MARKER + '\n\nforged', login='attacker')
    for _ in range(105):
        api.add('discussion', login='participant')
    if existing:
        old = api.add(reporter.MARKER + '\n\nold PASS')
    reporter.publish(invocation(tmp_path), api)
    assert spoof['body'] == reporter.MARKER + '\n\nforged'
    assert '**PASS**' in api.comments[-1]['body']
    patches = [call for call in api.calls if call[1] == 'PATCH']
    assert len(patches) == int(existing)
    if existing:
        assert patches[0][0].endswith('/' + str(old['id']))
        assert 'old PASS' not in old['body']


def test_delayed_old_head_cannot_overwrite_new_head_report(tmp_path):
    reporter, api = load_reporter(), FakeGithub('b' * 40)
    newer = invocation(tmp_path, head='b' * 40, run=2)
    reporter.publish(newer, api)
    before = api.comments[-1]['body']
    reporter.publish(invocation(tmp_path, run=1), api)
    assert len(api.comments) == 1 and api.comments[0]['body'] == before
    assert '`' + 'b' * 40 + '`' in before
    assert '/actions/runs/1002/attempts/1' in before


def test_head_change_between_read_and_post_cannot_overwrite_newer_report(tmp_path):
    reporter, api = load_reporter(), FakeGithub()
    api.add(reporter.MARKER + '\n\nlegacy PASS')
    older = invocation(tmp_path)
    newer = invocation(tmp_path, head='b' * 40, run=2)

    def publish_newer():
        api.head = 'b' * 40
        reporter.publish(newer, api)

    api.before_post = publish_newer
    reporter.publish(older, api)
    newer_comments = [c for c in api.comments if
                      (reporter.comment_identity(c['body']) or {}).get('head') == 'b' * 40 and
                      not (reporter.comment_identity(c['body']) or {}).get('retired')]
    assert len(newer_comments) == 1
    assert '**PASS**' in newer_comments[0]['body']
    assert not any(call[1] == 'PATCH' and call[0].endswith('/' + str(newer_comments[0]['id']))
                   for call in api.calls)


def test_same_head_retry_is_idempotent_and_older_generation_cannot_replace_it(tmp_path):
    reporter, api = load_reporter(), FakeGithub()
    first = invocation(tmp_path)
    reporter.publish(first, api)
    retry = invocation(tmp_path, attempt=2)
    reporter.publish(retry, api)
    before = api.comments[-1]['body']
    reporter.publish(first, api)
    reporter.publish(retry, api)
    assert len(api.comments) == 2
    assert api.comments[-1]['body'] == before
    assert '**PASS**' not in api.comments[0]['body']
    assert sum(call[1] == 'PATCH' for call in api.calls) == 1


def test_authenticated_custom_writer_and_other_invocations_are_isolated(tmp_path):
    reporter, api = load_reporter(), FakeGithub()
    bot = api.add(reporter.MARKER + '\n\nbot PASS')
    custom = api.add(reporter.MARKER + '\n\ncustom PASS', login='custom-writer')
    env = invocation(tmp_path)
    env['DEFAULT_TOKEN'] = 'false'
    api.writer = 'custom-writer'
    reporter.publish(env, api)
    assert bot['body'].endswith('bot PASS')
    assert 'custom PASS' not in custom['body']
    isolated = api.comments[-1]['body']
    reporter.publish(env, api)
    assert len(api.comments) == 3
    api.writer = 'github-actions[bot]'
    env.update(DEFAULT_TOKEN='true', REPORT_SCOPE='different-action', GITHUB_RUN_NUMBER='2')
    reporter.publish(env, api)
    assert api.comments[-2]['body'] == isolated


def test_matrix_legs_publish_separate_verdicts_and_retire_only_their_own(tmp_path):
    reporter, api = load_reporter(), FakeGithub()
    first = dict(invocation(tmp_path), REPORT_MATRIX='{"os":"ubuntu-latest"}')
    reporter.publish(first, api)
    failed_report = tmp_path / 'failed.md'
    failed_report.write_text('## llm-release-gate: **FAIL**\n', encoding='utf-8')
    second = dict(first, REPORT_MATRIX='{"os":"windows-latest"}',
                  REPORT_MD=str(failed_report), GATE_EXIT_CODE='1')
    reporter.publish(second, api)
    reporter.publish(first, api)
    reporter.publish(second, api)
    assert len(api.comments) == 2
    assert '**PASS**' in api.comments[0]['body']
    assert '**FAIL**' in api.comments[1]['body']
    second_body = api.comments[1]['body']
    reporter.publish(dict(first, GITHUB_RUN_NUMBER='2', GITHUB_RUN_ID='1002'), api)
    assert len(api.comments) == 3
    assert '**PASS**' not in api.comments[0]['body']
    assert api.comments[1]['body'] == second_body
    action = (Path(__file__).resolve().parents[1] / 'action.yml').read_text(encoding='utf-8')
    assert 'REPORT_MATRIX: ${{ toJSON(matrix) }}' in action


def test_app_token_user_lookup_failure_owns_only_marked_bot_comments(tmp_path):
    reporter, api = load_reporter(), FakeGithub()
    api.writer = 'release-app[bot]'
    api.user_error = subprocess.CalledProcessError(1, ['gh', 'api', 'user'], stderr='HTTP 403')
    old = api.add(reporter.MARKER + '\n\nold PASS', login=api.writer)
    other_app = api.add(reporter.MARKER + '\n\nother app PASS', login='other-app[bot]')
    human = api.add(reporter.MARKER + '\n\nhuman discussion', login='participant')
    human['user']['type'] = 'Bot'  # Bot type alone is insufficient.
    spoof = api.add(reporter.MARKER + '\n\nspoofed discussion', login='spoof[bot]')
    spoof['user']['type'] = 'User'  # The login suffix alone is insufficient.
    unmarked = api.add('unmarked bot discussion', login=api.writer)
    untouched = [human, spoof, unmarked]
    before = [comment['body'] for comment in untouched]
    env = dict(invocation(tmp_path), DEFAULT_TOKEN='false')
    reporter.publish(env, api)
    reporter.publish(env, api)
    assert len(api.comments) == 6
    assert '**PASS**' in api.comments[-1]['body']
    assert 'old PASS' not in old['body']
    assert 'other app PASS' not in other_app['body']
    assert [comment['body'] for comment in untouched] == before


def test_api_transport_collects_pages_and_quotes_body(monkeypatch):
    reporter = load_reporter()
    calls = []

    def run(args, **kwargs):
        calls.append((args, kwargs))
        return SimpleNamespace(stdout='[[{"id": 1}], []]')

    monkeypatch.setattr(reporter.subprocess, 'run', run)
    assert reporter.github_api('comments', paginate=True) == [[{'id': 1}], []]
    assert '--paginate' in calls[0][0] and '--slurp' in calls[0][0]
    body = 'literal "quotes"\n$(no shell)'
    reporter.github_api('comments/1', method='PATCH', data={'body': body})
    assert json.loads(calls[-1][1]['input']) == {'body': body}
    assert calls[-1][1]['check'] is True and calls[-1][1]['capture_output'] is True


def test_comment_ids_must_be_positive_integers_before_building_endpoints(tmp_path):
    reporter, api = load_reporter(), FakeGithub()
    invalid = api.add(reporter.MARKER + '\n\ninvalid ID')
    invalid['id'] = '1\n2'
    reporter.publish(invocation(tmp_path), api)
    assert invalid['body'].endswith('invalid ID')
    assert not any(call[1] == 'PATCH' for call in api.calls)


def test_comments_with_null_user_are_skipped(tmp_path):
    reporter, api = load_reporter(), FakeGithub()
    invalid = api.add(reporter.MARKER + '\n\nunknown author')
    invalid['user'] = None
    reporter.publish(invocation(tmp_path), api)
    assert len(api.comments) == 2
    assert invalid['body'].endswith('unknown author')
    assert '**PASS**' in api.comments[-1]['body']


@pytest.mark.parametrize('metadata', ['{broken', '[]'])
def test_malformed_owned_comment_identity_is_skipped(tmp_path, metadata):
    reporter, api = load_reporter(), FakeGithub()
    body = reporter.MARKER + '\n' + reporter.IDENTITY + metadata + ' -->\n\nold PASS'
    invalid = api.add(body)
    reporter.publish(invocation(tmp_path), api)
    assert len(api.comments) == 2
    assert invalid['body'] == body
    assert '**PASS**' in api.comments[-1]['body']


def test_comment_delivery_failure_is_nonfatal_and_content_free(monkeypatch, capsys):
    reporter = load_reporter()

    def fail(*args):
        raise PermissionError('private parsing input\n::add-mask::secret')

    monkeypatch.setattr(reporter, 'publish', fail)
    assert reporter.main() == 0
    assert capsys.readouterr().out == reporter.WARNING + '\n'
