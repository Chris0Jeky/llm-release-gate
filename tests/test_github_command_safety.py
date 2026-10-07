"""Workflow command data must not become another output or a shell program."""

import os
from pathlib import Path
import shutil
import subprocess

import pytest

from conftest import gate_argv
from llm_release_gate import cli
from llm_release_gate.errors import GateConfigError

ROOT = Path(__file__).resolve().parents[1]


def parse_outputs(text):
    """Parse the documented single-line/heredoc forms, preserving payload bytes."""
    result = {}
    lines = iter(text.splitlines(keepends=True))
    for raw in lines:
        header = raw.rstrip('\r\n')
        if not header:
            continue
        if '<<' in header and ('=' not in header or header.index('<<') < header.index('=')):
            name, delimiter = header.split('<<', 1)
            body = []
            for line in lines:
                if line.rstrip('\r\n') == delimiter:
                    break
                body.append(line)
            else:
                raise AssertionError('unterminated multiline output')
            result[name] = ''.join(body)[:-1]  # Writer appends exactly one framing LF.
        else:
            name, value = header.split('=', 1)
            result[name] = value
    return result


@pytest.mark.parametrize('value', ['safe path', 'line1\nverdict=pass\n', 'line1\r\nverdict=pass',
    'carriage\rreturn', 'lrg_output_0\ntext', '\n', 'é ${not code} `literal`'])
def test_output_values_cannot_inject_a_second_assignment(tmp_path, monkeypatch, value):
    sink = tmp_path / 'outputs'
    monkeypatch.setenv('GITHUB_OUTPUT', str(sink))
    cli._emit_github_outputs({'verdict': 'fail', 'report-md': value})
    assert parse_outputs(sink.read_bytes().decode()) == {'verdict': 'fail', 'report-md': value}


@pytest.mark.parametrize('key', ['bad\nverdict', 'bad=name', 'bad<<EOF', '', 1])
def test_invalid_output_names_fail_before_append(tmp_path, monkeypatch, key):
    sink = tmp_path / 'outputs'
    sink.write_text('old=value\n')
    monkeypatch.setenv('GITHUB_OUTPUT', str(sink))
    with pytest.raises(GateConfigError):
        cli._emit_github_outputs({'safe': 'new', key: 'bad'})
    assert sink.read_text() == 'old=value\n'


@pytest.mark.parametrize('variable', ['GITHUB_OUTPUT', 'GITHUB_STEP_SUMMARY'])
@pytest.mark.parametrize('role', ['dataset', 'fixture', 'report', 'lock'])
def test_github_sink_cannot_destroy_inputs_or_published_evidence(mini_gate, monkeypatch, variable, role, capsys):
    paths = mini_gate()
    out = Path(paths['out'])
    if role == 'dataset':
        sink = Path(paths['dataset'])
    elif role == 'fixture':
        sink = paths['tmp'] / 'fixtures/candidate.json'
    else:
        out.mkdir()
        sink = out / ('report.md' if role == 'report' else '.llm-release-gate.lock')
    before = sink.read_bytes() if sink.exists() else None
    monkeypatch.setenv(variable, str(sink))
    assert cli.main(gate_argv(paths)) == 2
    assert (sink.read_bytes() if sink.exists() else None) == before
    assert not (out / 'report.json').exists()
    assert 'Traceback' not in capsys.readouterr().err


@pytest.mark.parametrize('link', ['symlink', 'hardlink'])
def test_command_sink_alias_to_input_is_refused(mini_gate, monkeypatch, link):
    paths = mini_gate()
    source, sink = Path(paths['dataset']), paths['tmp'] / 'command-alias'
    try:
        os.symlink(source, sink) if link == 'symlink' else os.link(source, sink)
    except OSError:
        pytest.skip('links unavailable')
    before = source.read_bytes()
    monkeypatch.setenv('GITHUB_OUTPUT', str(sink))
    assert cli.main(gate_argv(paths)) == 2
    assert source.read_bytes() == before
    assert not Path(paths['out']).exists()


def test_command_sinks_must_not_alias_each_other(mini_gate, monkeypatch):
    paths = mini_gate()
    sink = paths['tmp'] / 'both-sinks'
    sink.write_text('unchanged')
    for variable in ('GITHUB_OUTPUT', 'GITHUB_STEP_SUMMARY'):
        monkeypatch.setenv(variable, str(sink))
    assert cli.main(gate_argv(paths)) == 2
    assert sink.read_text() == 'unchanged'
    assert not Path(paths['out']).exists()


@pytest.mark.skipif(shutil.which('bash') is None, reason='Action requires Bash')
@pytest.mark.parametrize('value,expected', [('0', 0), ('1', 1), ('2', 2), ('127', 2),
    ('256', 2), ('-1', 2), ('', 2), ('bad', 2), ('$(touch injected)', 2)])
def test_enforcement_treats_status_as_data_and_fails_closed(tmp_path, value, expected):
    action = (ROOT / 'action.yml').read_text()
    body = action.split('    - name: Enforce gate verdict\n', 1)[1].split('      run: |\n', 1)[1]
    script = '\n'.join(line[8:] for line in body.splitlines())
    # Emulate runner interpolation only for the old vulnerable implementation.
    script = script.replace('${{ steps.gate.outputs.cli-exit }}', value)
    result = subprocess.run([shutil.which('bash'), '-c', script], cwd=tmp_path,
                            env=dict(os.environ, GATE_EXIT_CODE=value), capture_output=True, timeout=10)
    assert not (tmp_path / 'injected').exists()
    assert result.returncode == expected


def test_action_enforcement_does_not_interpolate_status_into_script():
    action = (ROOT / 'action.yml').read_text()
    step = action.split('    - name: Enforce gate verdict\n', 1)[1]
    env, script = step.split('      run: |\n', 1)
    assert 'GATE_EXIT_CODE: ${{ steps.gate.outputs.cli-exit }}' in env
    assert '${{' not in script


@pytest.mark.parametrize('value', ['bad\x00value', '\ud800'])
def test_unencodable_output_is_refused_without_partial_commands(tmp_path, monkeypatch, value):
    sink = tmp_path / 'outputs'
    sink.write_text('old=value\n')
    monkeypatch.setenv('GITHUB_OUTPUT', str(sink))
    with pytest.raises(GateConfigError):
        cli._emit_github_outputs({'safe': 'new', 'bad': value})
    assert sink.read_text() == 'old=value\n'


def test_hosted_workflow_checks_literal_output_after_runner_parsing():
    workflow = (ROOT / '.github/workflows/ci.yml').read_text()
    assert 'id: literal_outputs' in workflow
    assert 'LITERAL_PAYLOAD: ${{ steps.literal_outputs.outputs.literal }}' in workflow
    assert 'INJECTED_OUTPUT: ${{ steps.literal_outputs.outputs.injected }}' in workflow
