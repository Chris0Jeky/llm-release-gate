"""Untrusted diagnostics must stay data in Actions log streams."""

import json
import os
from pathlib import Path
import subprocess
import sys
import shutil
import textwrap

import pytest

from conftest import gate_argv, write_json
from llm_release_gate import cli
from llm_release_gate.errors import GateConfigError


def test_gate_logs_neutralize_commands_without_changing_report(mini_gate):
    payload = "v1\n::warning::injected\r\n::add-mask::secret"
    paths = mini_gate(pricing={"version": payload, "currency": "USD", "models": {
        "other": {"input_per_mtok": 0, "output_per_mtok": 0}}},
        thresholds={"rules": [{"metric": "cost.total_usd", "max_value": 1}]})
    config = json.loads(Path(paths['candidate']).read_text(encoding='utf-8'))
    config['model'] = "model\n::warning::model\n::add-mask::model"
    write_json(Path(paths['candidate']), config)
    fixture = paths['tmp'] / 'fixtures/candidate.json'
    doc = json.loads(fixture.read_text(encoding='utf-8'))
    doc['responses'] = {config['model']: doc['responses'].pop('m-cand')}
    write_json(fixture, doc)
    output = subprocess.run([sys.executable, '-m', 'llm_release_gate', *gate_argv(paths)],
                            env=dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[1] / 'src')),
                            capture_output=True, timeout=10)
    assert output.returncode == 1
    assert b'::warning::' not in output.stdout + output.stderr
    assert b'::add-mask::' not in output.stdout + output.stderr
    assert b'\\n' in output.stdout
    report = json.loads((Path(paths['out']) / 'report.json').read_text(encoding='utf-8'))
    assert report['gate']['verdict'] == 'fail'
    assert report['inputs']['pricing_table']['version'] == payload
    assert payload in report['rules'][0]['message']


@pytest.mark.parametrize('error', [GateConfigError, RuntimeError])
def test_nested_exception_log_is_inert(mini_gate, monkeypatch, capsys, error):
    def fail(*args):
        try:
            raise ValueError('nested\n::add-mask::secret')
        except ValueError as cause:
            raise error('outer\r\n::warning::forged') from cause

    monkeypatch.setattr(cli, 'load_dataset', fail)
    assert cli.main(gate_argv(mini_gate())) == 2
    output = capsys.readouterr()
    assert '::warning::' not in output.err
    assert '::add-mask::' not in output.err
    assert 'outer' in output.err


def test_argument_errors_cannot_emit_workflow_commands(capsys):
    with pytest.raises(SystemExit) as exc:
        cli.main(['--unknown\n::warning::forged\r::add-mask::secret'])
    assert exc.value.code == 2
    output = capsys.readouterr()
    assert '::warning::' not in output.err and '::add-mask::' not in output.err


def test_json_diagnostics_preserve_values_without_workflow_commands(monkeypatch, capsys):
    from llm_release_gate import audit

    receipt = {'policy_verdict': 'fail', 'note': 'a\\::warning::forged\n::add-mask::secret'}
    monkeypatch.setattr(audit, 'audit_bundle', lambda *args, **kwargs: receipt)
    assert cli.main(['audit', '--bundle', 'unused', '--thresholds', 'unused', '--json']) == 1
    output = capsys.readouterr().out
    assert '::warning::' not in output and '::add-mask::' not in output
    assert json.loads(output) == receipt


def test_action_self_test_scripts_capture_the_real_gate_stream(tmp_path, monkeypatch, action_bash):
    root = Path(__file__).resolve().parents[1]
    workflow = (root / '.github/workflows/ci.yml').read_text(encoding='utf-8')

    def workflow_python(name):
        step = workflow.split('      - name: ' + name + '\n', 1)[1].split('\n      - name:', 1)[0]
        script = textwrap.dedent(step.split('        run: |\n', 1)[1])
        return script.split("<<'PYCODE'\n", 1)[1].rsplit('\nPYCODE', 1)[0]

    shutil.copytree(root / 'examples/rag-support-bot', tmp_path / 'examples/rag-support-bot')
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv('RUNNER_TEMP', str(tmp_path))
    exec(workflow_python('Prepare adversarial pricing and model diagnostics'), {})
    action = (root / 'action.yml').read_text(encoding='utf-8')
    step = action.split('    - name: Run gate\n', 1)[1].split('\n    # Bind reports', 1)[0]
    script = textwrap.dedent(step.split('      run: |\n', 1)[1])
    env = dict(os.environ, PYTHONPATH=str(root / 'src'), PYTHONIOENCODING='utf-8',
               PATH=str(Path(sys.executable).parent) + os.pathsep + os.environ['PATH'],
               BASH_ENV=str(tmp_path / 'capture-gate.sh'), GITHUB_OUTPUT=str(tmp_path / 'outputs'),
               GITHUB_STEP_SUMMARY=str(tmp_path / 'summary'), IN_OUT='out/action-log-safety',
               IN_MAX_INPUT_BYTES='', IN_REQUIRE_BINDING='false')
    for role in ('dataset', 'baseline', 'candidate', 'scorers', 'thresholds', 'pricing'):
        env['IN_' + role.upper()] = f'out/action-log-inputs/{role}.json'
    result = subprocess.run([action_bash, '-c', script], env=env, capture_output=True, timeout=20)
    assert result.returncode == 0, result.stderr
    assert b'::warning::' not in result.stdout and b'::add-mask::' not in result.stdout
    assert 'cli-exit=1' in (tmp_path / 'outputs').read_text(encoding='utf-8')
    monkeypatch.setenv('LOG_OUTCOME', 'failure')
    monkeypatch.setenv('LOG_VERDICT', 'fail')
    exec(workflow_python('Assert runner log data is inert and structured evidence is complete'), {})
