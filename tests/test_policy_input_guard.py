"""The pure policy evaluator must reject malformed inputs before making a verdict."""

import pytest

from llm_release_gate.errors import GateConfigError
from llm_release_gate.gate import evaluate_thresholds
from llm_release_gate.loading import ThresholdRule, Thresholds
from llm_release_gate.metrics import HIGHER, LOWER, rate_metric, scalar_metric, unavailable_metric


def evaluate(metric=None, rule=None, baseline=None):
    good = scalar_metric(0.8, 'rate', HIGHER)
    errors = rate_metric(0, 1, LOWER)
    return evaluate_thresholds(Thresholds([rule or ThresholdRule('q', {'min_value': 0.5})], '', ''),
        {'q': good if baseline is None else baseline, 'errors.error_rate': errors},
        {'q': good if metric is None else metric, 'errors.error_rate': errors})


@pytest.mark.parametrize('value', [float('nan'), float('inf'), -float('inf'), True, False, '0.9', [], {}])
def test_available_value_must_be_a_finite_number_not_boolean(value):
    metric = scalar_metric(0.8, 'rate', HIGHER)
    metric['value'] = value
    with pytest.raises(GateConfigError, match='q.*candidate'):
        evaluate(metric=metric)


@pytest.mark.parametrize('available', ['false', 'true', 1, 0, [], None])
def test_availability_is_literal_boolean(available):
    metric = scalar_metric(0.8, 'rate', HIGHER)
    metric['available'] = available
    with pytest.raises(GateConfigError, match='available'):
        evaluate(metric=metric)


@pytest.mark.parametrize('constraints', [{}, {'typo': 0.1}, {'min_value': True},
    {'min_value': float('nan')}, {'min_value': float('inf')}, {'min_value': '0.5'}, []])
def test_invalid_constraint_never_becomes_pass_or_skip(constraints):
    rule = ThresholdRule('q', constraints, on_unavailable='skip')
    with pytest.raises(GateConfigError, match='threshold'):
        evaluate(metric=unavailable_metric('rate', HIGHER, 'missing'), rule=rule)


@pytest.mark.parametrize('field,value', [('metric', []), ('metric', ''), ('level', 'maybe'),
    ('level', {}), ('on_unavailable', 'allow'), ('on_unavailable', {})])
def test_invalid_rule_metadata_is_clean_configuration_error(field, value):
    rule = ThresholdRule('q', {'min_value': 0.5})
    setattr(rule, field, value)
    with pytest.raises(GateConfigError, match='threshold'):
        evaluate(metric=unavailable_metric('rate', HIGHER, 'missing'), rule=rule)


def test_overflowing_comparison_is_not_a_nonfinite_verdict_observation():
    with pytest.raises(GateConfigError, match='arithmetic'):
        evaluate(metric=scalar_metric(1e308, 'usd', LOWER),
                 baseline=scalar_metric(-1e308, 'usd', LOWER),
                 rule=ThresholdRule('q', {'max_increase_abs': 1}))


def test_exact_large_integer_aggregate_need_not_be_coerced_to_float():
    result = evaluate(metric=scalar_metric(10**400, 'tokens', LOWER),
                      rule=ThresholdRule('q', {'max_value': 100}))
    assert result[0]['verdict'] == 'fail'


def test_candidate_only_rule_does_not_need_unavailable_baseline_value():
    assert evaluate(baseline=unavailable_metric('rate', HIGHER, 'missing'))[0]['verdict'] == 'pass'
