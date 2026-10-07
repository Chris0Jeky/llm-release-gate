"""Publishing evidence must never destroy inputs or an earlier complete bundle."""

import json
import os
from pathlib import Path

import pytest

from conftest import gate_argv
from llm_release_gate import cli

NAMES = ('report.json', 'report.md', 'report.html', 'manifest.json')


def previous_bundle(paths):
    assert cli.main(gate_argv(paths)) == 0
    out = Path(paths['out'])
    before = {name: (out / name).read_bytes() for name in NAMES}
    cfg = Path(paths['candidate'])
    data = json.loads(cfg.read_text())
    data['name'] = 'new-generation'
    cfg.write_text(json.dumps(data))
    return out, before


@pytest.mark.parametrize('role', ['dataset', 'baseline', 'candidate', 'scorers', 'thresholds', 'pricing'])
def test_output_cannot_replace_an_input(mini_gate, role, capsys):
    paths = mini_gate()
    out = Path(paths['out'])
    out.mkdir()
    source = out / 'report.json'
    source.write_bytes(Path(paths[role]).read_bytes())
    # Preserve resolution of fixture paths when moving a run config.
    if role in ('baseline', 'candidate'):
        data = json.loads(source.read_text())
        data['provider_options']['fixtures'] = str(paths['tmp'] / data['provider_options']['fixtures'])
        source.write_text(json.dumps(data))
    paths[role] = str(source)
    before = source.read_bytes()
    assert cli.main(gate_argv(paths)) == 2
    assert source.read_bytes() == before
    assert set(p.name for p in out.iterdir()) == {'report.json'}
    err = capsys.readouterr().err
    assert 'output' in err and 'input' in err and 'Traceback' not in err


def test_output_cannot_replace_transitive_fixture(mini_gate, capsys):
    paths = mini_gate()
    out = Path(paths['out'])
    out.mkdir()
    source = out / 'manifest.json'
    source.write_bytes((paths['tmp'] / 'fixtures/candidate.json').read_bytes())
    cfg = Path(paths['candidate'])
    data = json.loads(cfg.read_text())
    data['provider_options']['fixtures'] = str(source)
    cfg.write_text(json.dumps(data))
    before = source.read_bytes()
    assert cli.main(gate_argv(paths)) == 2
    assert source.read_bytes() == before
    assert set(p.name for p in out.iterdir()) == {'manifest.json'}
    assert 'input' in capsys.readouterr().err


@pytest.mark.parametrize('link', ['symlink', 'hardlink'])
def test_alias_to_input_is_refused_before_any_report_write(mini_gate, link):
    paths = mini_gate()
    out = Path(paths['out'])
    out.mkdir()
    source = Path(paths['dataset'])
    target = out / 'report.html'
    try:
        os.symlink(source, target) if link == 'symlink' else os.link(source, target)
    except OSError:
        pytest.skip('link creation unsupported')
    before = source.read_bytes()
    assert cli.main(gate_argv(paths)) == 2
    assert source.read_bytes() == before
    assert set(p.name for p in out.iterdir()) == {'report.html'}


def test_invalid_later_destination_preserves_previous_reports(mini_gate, capsys):
    paths = mini_gate()
    out, before = previous_bundle(paths)
    (out / 'manifest.json').unlink()
    (out / 'manifest.json').mkdir()
    assert cli.main(gate_argv(paths)) == 2
    for name in NAMES[:-1]:
        assert (out / name).read_bytes() == before[name]
    assert 'Traceback' not in capsys.readouterr().err


@pytest.mark.parametrize('renderer', ['render_html', 'build_manifest'])
def test_render_failure_preserves_previous_complete_bundle(mini_gate, monkeypatch, renderer):
    paths = mini_gate()
    out, before = previous_bundle(paths)
    def broken(*args, **kwargs):
        raise RuntimeError('simulated rendering failure')
    monkeypatch.setattr(cli, renderer, broken)
    assert cli.main(gate_argv(paths)) == 2
    assert {p.name: p.read_bytes() for p in out.iterdir()} == before


def test_diagnostic_run_cannot_replace_its_dataset(mini_gate):
    paths = mini_gate()
    out = Path(paths['out'])
    out.mkdir()
    source = out / 'run.json'
    before = Path(paths['dataset']).read_bytes()
    source.write_bytes(before)
    args = ['run', '--dataset', str(source), '--config', paths['candidate'],
            '--scorers', paths['scorers'], '--out', str(out)]
    assert cli.main(args) == 2
    assert source.read_bytes() == before


@pytest.mark.parametrize('name', NAMES)
def test_dangling_output_symlink_is_not_followed(mini_gate, name):
    paths = mini_gate()
    out = Path(paths['out'])
    out.mkdir()
    outside = paths['tmp'] / 'not-an-output'
    try:
        (out / name).symlink_to(outside)
    except OSError:
        pytest.skip('symlinks unavailable')
    assert cli.main(gate_argv(paths)) == 2
    assert not outside.exists()
    assert set(p.name for p in out.iterdir()) == {name}


@pytest.mark.parametrize('fail_after', [0, 1, 2, 3])
def test_replace_failure_rolls_back_entire_bundle(mini_gate, monkeypatch, fail_after, capsys):
    paths = mini_gate()
    out, before = previous_bundle(paths)
    real_replace = os.replace
    commits = []
    def fail_once(source, dest):
        if Path(source).name.startswith('new-'):
            if len(commits) == fail_after:
                commits.append('failed')
                raise OSError('simulated publish failure')
            commits.append(dest)
        return real_replace(source, dest)
    monkeypatch.setattr(os, 'replace', fail_once)
    assert cli.main(gate_argv(paths)) == 2
    assert {p.name: p.read_bytes() for p in out.iterdir()} == before
    assert 'Traceback' not in capsys.readouterr().err


def test_another_publisher_lock_is_not_removed(mini_gate, capsys):
    paths = mini_gate()
    out = Path(paths['out'])
    out.mkdir()
    lock = out / '.llm-release-gate.lock'
    lock.write_text('other writer')
    assert cli.main(gate_argv(paths)) == 2
    assert lock.read_text() == 'other writer'
    assert set(p.name for p in out.iterdir()) == {lock.name}
    assert 'lock' in capsys.readouterr().err


def test_publication_preserves_unrelated_files(mini_gate):
    paths = mini_gate()
    out = Path(paths['out'])
    out.mkdir()
    unrelated = out / 'keep.txt'
    unrelated.write_text('keep me')
    assert cli.main(gate_argv(paths)) == 0
    assert unrelated.read_text() == 'keep me'
    assert set(p.name for p in out.iterdir()) == set(NAMES) | {'keep.txt'}


@pytest.mark.parametrize('existing', [True, False])
def test_staging_failure_never_publishes_partial_evidence(mini_gate, monkeypatch, existing):
    paths = mini_gate()
    if existing:
        out, before = previous_bundle(paths)
    else:
        out, before = Path(paths['out']), {}
    real_write = Path.write_bytes
    def fail_staging(path, data):
        if path.name == 'new-1':
            raise OSError('simulated disk full')
        return real_write(path, data)
    monkeypatch.setattr(Path, 'write_bytes', fail_staging)
    assert cli.main(gate_argv(paths)) == 2
    assert {p.name: p.read_bytes() for p in out.iterdir()} == before


def test_failed_rollback_retains_recovery_and_blocks_new_writer(mini_gate, monkeypatch, capsys):
    paths = mini_gate()
    out, before = previous_bundle(paths)
    real_replace = os.replace
    def fail_publication_and_rollback(source, dest):
        if Path(source).name in ('new-1', 'old-0'):
            raise OSError('simulated replacement failure')
        return real_replace(source, dest)
    monkeypatch.setattr(os, 'replace', fail_publication_and_rollback)
    assert cli.main(gate_argv(paths)) == 2
    assert 'rollback was incomplete' in capsys.readouterr().err
    stage, = list(out.glob('.lrg-stage-*'))
    assert (stage / 'old-0').read_bytes() == before['report.json']
    assert (out / '.llm-release-gate.lock').exists()
    recovery = json.loads((stage / 'recovery.json').read_text())
    assert recovery['files'][0]['destination'] == str(out / 'report.json')
    assert recovery['files'][0]['backup'] == 'old-0'
    monkeypatch.setattr(os, 'replace', real_replace)
    assert cli.main(gate_argv(paths)) == 2
    assert 'lock' in capsys.readouterr().err


def test_replacing_regular_hardlink_does_not_mutate_unrelated_file(mini_gate):
    paths = mini_gate()
    out = Path(paths['out'])
    out.mkdir()
    unrelated = paths['tmp'] / 'not-an-input'
    unrelated.write_text('unrelated bytes')
    try:
        os.link(unrelated, out / 'report.json')
    except OSError:
        pytest.skip('hardlinks unavailable')
    assert cli.main(gate_argv(paths)) == 0
    assert unrelated.read_text() == 'unrelated bytes'


def test_input_capture_does_not_leak_across_cli_calls(mini_gate):
    paths = mini_gate()
    from llm_release_gate.loading import loaded_input_sources
    assert cli.main(gate_argv(paths)) == 0
    assert not loaded_input_sources()
    paths['candidate'] = 'missing-input.json'
    assert cli.main(gate_argv(paths)) == 2
    assert not loaded_input_sources()
