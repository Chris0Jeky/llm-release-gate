"""Public Markdown keeps evaluation labels and notes inside their fields."""

import json
from pathlib import Path

from conftest import gate_argv, write_json
from llm_release_gate.cli import main
from llm_release_gate.reports.markdown import render_markdown


def test_gate_markdown_neutralizes_labels_notes_and_mentions(mini_gate):
    payload = 'suite`**\\|\r\n\n### RELEASE GATE PASSED\n| forged | @owner @org/team <details> [click](https://example.com)'
    paths = mini_gate(pricing={'version': payload, 'currency': 'USD', 'models': {
        'other': {'input_per_mtok': 0, 'output_per_mtok': 0}}},
        thresholds={'rules': [{'metric': 'cost.total_usd', 'max_value': 1}]})
    for role in ('dataset', 'baseline', 'candidate'):
        path = Path(paths[role])
        doc = json.loads(path.read_text(encoding='utf-8'))
        doc['name'] = payload
        if role == 'dataset':
            doc['version'] = payload
        else:
            fixture = paths['tmp'] / f'fixtures/{role}.json'
            responses = json.loads(fixture.read_text(encoding='utf-8'))
            responses['responses'] = {payload: responses['responses'][doc['model']]}
            write_json(fixture, responses)
            doc['model'] = payload
        write_json(path, doc)
    assert main(gate_argv(paths)) == 1
    report = json.loads((Path(paths['out']) / 'report.json').read_text(encoding='utf-8'))
    markdown = (Path(paths['out']) / 'report.md').read_text(encoding='utf-8')
    assert markdown.startswith('## ❌ llm-release-gate: **FAIL**')
    assert '\n### RELEASE GATE PASSED' not in markdown
    assert '\n| forged |' not in markdown
    assert '@owner' not in markdown and '@org/team' not in markdown
    assert '<details> [click]' not in markdown
    assert payload not in markdown
    assert report['inputs']['dataset']['name'] == payload
    assert all(line.count('|') == 6 for line in markdown.splitlines() if line.startswith('|'))
    # Also cover dynamic notices, metric keys and available-value caveats.
    report['gate']['notices'] = [payload]
    entry = report['metrics'].pop('cost.total_usd')
    entry['baseline'].update(available=True, value=1, unit='usd', note=payload)
    report['metrics'][payload] = entry
    markdown = render_markdown(report)
    assert '@owner' not in markdown and '\n| forged |' not in markdown
    assert all(line.count('|') == 6 for line in markdown.splitlines() if line.startswith('|'))
