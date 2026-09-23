"""Pin the current behaviour of llm_release_gate.reports fmt_value/fmt_delta.

These tests pin observed formatting exactly (exact-string assertions), so any
change to the formatters breaks them. Unavailable handling, rounding, signs and
the rate special-cases are all pinned as implemented today.
"""


from llm_release_gate.reports import fmt_delta, fmt_value


# --- fmt_value: usd ---


def test_fmt_value_usd():
    m = {"available": True, "unit": "usd", "value": 0.0025}
    assert fmt_value(m) == "$0.002500"


def test_fmt_value_usd_zero_boundary():
    assert fmt_value({"available": True, "unit": "usd", "value": 0.0}) == "$0.000000"


# --- fmt_value: ms ---


def test_fmt_value_ms_rounds_to_whole():
    assert fmt_value({"available": True, "unit": "ms", "value": 123.6}) == "124 ms"


# --- fmt_value: tokens ---


def test_fmt_value_tokens_groups_thousands():
    assert fmt_value({"available": True, "unit": "tokens", "value": 1234567.0}) == "1,234,567"


def test_fmt_value_tokens_zero_boundary():
    assert fmt_value({"available": True, "unit": "tokens", "value": 0}) == "0"


# --- fmt_value: rate ---


def test_fmt_value_rate_counts_plus_percent():
    m = {"available": True, "unit": "rate", "value": 0.875, "numerator": 7, "denominator": 8}
    assert fmt_value(m) == "7/8 (87.5%)"


def test_fmt_value_rate_zero_over_zero_boundary():
    m = {"available": True, "unit": "rate", "value": 0.0, "numerator": 0, "denominator": 0}
    assert fmt_value(m) == "0/0 (0.0%)"


# --- fmt_value: default fallback ---


def test_fmt_value_default_unit_uses_general_format():
    assert fmt_value({"available": True, "unit": "score", "value": 0.123456789}) == "0.123457"


def test_fmt_value_unknown_unit_falls_back_to_general_format():
    assert fmt_value({"available": True, "unit": "custom", "value": 1.5}) == "1.5"


# --- fmt_value: unavailable ("None" case) ---


def test_fmt_value_unavailable_returns_word():
    m = {"available": False, "unit": "usd", "value": 0.0025}
    assert fmt_value(m) == "unavailable"


def test_fmt_value_unavailable_ignores_unit_branch():
    m = {"available": False, "unit": "rate", "value": 0.875, "numerator": 7, "denominator": 8}
    assert fmt_value(m) == "unavailable"


# --- fmt_delta: None -> em dash ---


def test_fmt_delta_missing_delta_returns_em_dash():
    assert fmt_delta({"candidate": {"unit": "usd"}}) == "\u2014"


def test_fmt_delta_explicit_none_returns_em_dash():
    assert fmt_delta({"candidate": {"unit": "usd"}, "delta": None}) == "\u2014"


def test_fmt_delta_none_needs_no_candidate_key():
    assert fmt_delta({}) == "\u2014"


# --- fmt_delta: rate percentage-point form ---


def test_fmt_delta_rate_increase_in_percentage_points():
    entry = {"candidate": {"unit": "rate"}, "delta": {"abs": 0.025, "pct": 5.0}}
    assert fmt_delta(entry) == "+2.5pp"


def test_fmt_delta_rate_ignores_pct_field():
    entry = {"candidate": {"unit": "rate"}, "delta": {"abs": 0.025, "pct": None}}
    assert fmt_delta(entry) == "+2.5pp"


def test_fmt_delta_rate_decrease_sign():
    entry = {"candidate": {"unit": "rate"}, "delta": {"abs": -0.012, "pct": -3.0}}
    assert fmt_delta(entry) == "-1.2pp"


# --- fmt_delta: absolute plus percent (usd/ms/tokens) ---


def test_fmt_delta_usd_increase_with_percent():
    entry = {"candidate": {"unit": "usd"}, "delta": {"abs": 0.0005, "pct": 25.0}}
    assert fmt_delta(entry) == "+0.000500 (+25.0%)"


def test_fmt_delta_usd_decrease_with_percent():
    entry = {"candidate": {"unit": "usd"}, "delta": {"abs": -0.0005, "pct": -25.0}}
    assert fmt_delta(entry) == "-0.000500 (-25.0%)"


def test_fmt_delta_usd_none_pct_omits_parens():
    entry = {"candidate": {"unit": "usd"}, "delta": {"abs": 0.0005, "pct": None}}
    assert fmt_delta(entry) == "+0.000500"


def test_fmt_delta_ms_increase_with_percent():
    entry = {"candidate": {"unit": "ms"}, "delta": {"abs": 12.0, "pct": 10.0}}
    assert fmt_delta(entry) == "+12 ms (+10.0%)"


def test_fmt_delta_ms_decrease_with_percent():
    entry = {"candidate": {"unit": "ms"}, "delta": {"abs": -12.0, "pct": -10.0}}
    assert fmt_delta(entry) == "-12 ms (-10.0%)"


def test_fmt_delta_tokens_increase_with_percent():
    entry = {"candidate": {"unit": "tokens"}, "delta": {"abs": 1500.0, "pct": 15.0}}
    assert fmt_delta(entry) == "+1,500 (+15.0%)"


def test_fmt_delta_tokens_none_pct_omits_parens():
    entry = {"candidate": {"unit": "tokens"}, "delta": {"abs": 1500.0, "pct": None}}
    assert fmt_delta(entry) == "+1,500"


def test_fmt_delta_zero_signed_plus_boundary():
    entry = {"candidate": {"unit": "usd"}, "delta": {"abs": 0.0, "pct": 0.0}}
    assert fmt_delta(entry) == "+0.000000 (+0.0%)"


# --- fmt_delta: unit fallback ---


def test_fmt_delta_unknown_unit_falls_back_to_general_format():
    entry = {"candidate": {"unit": "score"}, "delta": {"abs": 0.05, "pct": 10.0}}
    assert fmt_delta(entry) == "+0.05 (+10.0%)"


def test_fmt_delta_unknown_unit_none_pct_omits_parens():
    entry = {"candidate": {"unit": "score"}, "delta": {"abs": 0.05, "pct": None}}
    assert fmt_delta(entry) == "+0.05"


