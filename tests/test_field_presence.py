"""Missing fields must never equal a legitimate JSON value used as a marker."""

import json
from pathlib import Path

import pytest

from conftest import gate_argv
from llm_release_gate.cli import main
from llm_release_gate.adapters.extraction import ExtractionAdapter
from llm_release_gate.loading import DatasetItem
from llm_release_gate.scorers.quality import FieldMatchScorer


@pytest.mark.parametrize('key', ['value', '', 'café'])
@pytest.mark.parametrize('present', [False, True])
def test_literal_missing_marker_is_data_not_absence(key, present):
    item = DatasetItem('i', {'text': 'source'}, {'fields': {key: '<missing>'}})
    output = ExtractionAdapter().parse(json.dumps({key: '<missing>'} if present else {}), item)
    result = FieldMatchScorer({}).score_item(item, output)['quality.pass_rate']
    assert result['applicable'] is True
    assert result['passed'] is present
    assert result['detail'] == (None if present else f'{key}: field is <missing>')


@pytest.mark.parametrize('expected,actual', [(None, {}), (True, {'a': 1}),
    ({'nested': True}, {'a': {'nested': 1}}), (['<missing>'], {})])
def test_missing_null_and_json_type_distinctions_remain_failures(expected, actual):
    item = DatasetItem('i', {}, {'fields': {'a': expected}})
    output = ExtractionAdapter().parse(json.dumps(actual), item)
    assert FieldMatchScorer({}).score_item(item, output)['quality.pass_rate']['passed'] is False


@pytest.mark.parametrize('candidate', ['{}', '```json\n{}\n```'])
def test_missing_marker_field_is_blocked_by_real_extraction_gate(mini_gate, candidate):
    dataset = {'name': 'presence', 'version': '1', 'task': 'extraction', 'items': [
        {'id': 'r1', 'input': {'text': 'source'}, 'expected': {'fields': {'value': '<missing>'}}},
    ]}
    paths = mini_gate(dataset=dataset, scorers={'scorers': [{'type': 'field_match'}]},
        baseline_responses={'r1': {'text': '{"value":"<missing>"}'}},
        candidate_responses={'r1': {'text': candidate}},
        thresholds={'rules': [{'metric': 'quality.pass_rate', 'max_drop_abs': 0}]})
    for role in ('baseline', 'candidate'):
        path = Path(paths[role])
        cfg = json.loads(path.read_text())
        cfg['prompt']['template'] = '$text'
        path.write_text(json.dumps(cfg))
    assert main(gate_argv(paths)) == 1
    report = json.loads((Path(paths['out']) / 'report.json').read_text())
    assert report['metrics']['quality.pass_rate']['baseline']['value'] == 1
    assert report['metrics']['quality.pass_rate']['candidate']['value'] == 0
    assert report['runs']['candidate']['n_errors'] == 0  # scoring failure, not provider failure
    assert report['items'][0]['candidate']['scores']['quality.pass_rate']['detail'] == 'value: field is <missing>'
    assert main(['verify', '--bundle', paths['out'], '--require-pass']) == 1


def test_field_match_identity_versions_the_scoring_change():
    assert FieldMatchScorer({}).describe()['version'] == '3'
