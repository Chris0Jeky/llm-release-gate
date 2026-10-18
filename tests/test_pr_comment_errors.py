"""An evaluation error must retire a previously published PASS."""

from pathlib import Path

import pytest

from conftest import gate_argv, write_json
from llm_release_gate.cli import main
from pr_comment_fakes import FakeGithub, invocation, load_reporter


def test_action_attempts_error_comment_without_report_output():
    action = (Path(__file__).resolve().parents[1] / 'action.yml').read_text(encoding='utf-8')
    step = action.split('    - name: Comment on pull request\n', 1)[1].split('    - name: Enforce', 1)[0]
    assert "steps.gate.outputs.report-md != ''" not in step
    assert 'GATE_EXIT_CODE: ${{ steps.gate.outputs.cli-exit }}' in step


def test_green_then_invalid_head_retires_pass_without_exposing_input(mini_gate, tmp_path):
    reporter, api = load_reporter(), FakeGithub()
    paths = mini_gate()
    assert main(gate_argv(paths)) == 0
    first = invocation(tmp_path)
    first['REPORT_MD'] = str(Path(paths['out']) / 'report.md')
    reporter.publish(first, api)
    assert '**PASS**' in api.comments[0]['body']
    write_json(Path(paths['thresholds']), {'rules': [{'metric': 'private-unknown-metric', 'max_value': 0}]})
    assert main(gate_argv(paths)) == 2
    api.head = 'b' * 40
    second = invocation(tmp_path, head=api.head, run=2)
    # Even a stale report path must not be read after exit 2.
    second.update(GATE_EXIT_CODE='2', REPORT_MD=first['REPORT_MD'])
    reporter.publish(second, api)
    assert len(api.comments) == 2
    for comment in api.comments:
        assert '**PASS**' not in comment['body']
        assert 'unable to evaluate' in comment['body']
        assert 'private-unknown-metric' not in comment['body']
        assert '`' + api.head + '`' in comment['body']
        assert '/actions/runs/1002/attempts/1' in comment['body']


@pytest.mark.parametrize('exit_code', ['0', '1'])
@pytest.mark.parametrize('failure', ['missing', 'directory', 'invalid_utf8', 'permission'])
def test_unreadable_report_posts_error_and_retires_pass(tmp_path, monkeypatch, exit_code, failure):
    reporter, api = load_reporter(), FakeGithub()
    reporter.publish(invocation(tmp_path), api)
    current = invocation(tmp_path, run=2)
    report = Path(current['REPORT_MD'])
    if failure == 'missing':
        report.unlink()
    elif failure == 'directory':
        report.unlink()
        report.mkdir()
    elif failure == 'invalid_utf8':
        report.write_bytes(b"\xffprivate report")
    else:
        read_text = Path.read_text

        def denied(path, *args, **kwargs):
            if path == report:
                raise PermissionError('private report path')
            return read_text(path, *args, **kwargs)

        monkeypatch.setattr(Path, 'read_text', denied)
    current['GATE_EXIT_CODE'] = exit_code
    reporter.publish(current, api)
    assert len(api.comments) == 2
    for comment in api.comments:
        assert 'unable to evaluate' in comment['body']
        assert '**PASS**' not in comment['body']
        assert 'private report' not in comment['body']
        assert '`' + api.head + '`' in comment['body']
        assert '/actions/runs/1002/attempts/1' in comment['body']
    assert reporter.comment_identity(api.comments[0]['body'])['retired'] is True
