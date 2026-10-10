"""Report generation: sample counts shown, heuristics labeled, HTML escaped,
unavailable values explained."""

import json

import pytest

from llm_release_gate.cli import main
from llm_release_gate.metrics import percentile

from llm_release_gate.metrics import rate_metric
from conftest import GOOD_RESPONSE, gate_argv
from llm_release_gate.reports import verdict_word
from llm_release_gate.reports.markdown import render_markdown


def test_verdict_word_falls_back_to_upper():
    assert verdict_word("error") == "ERROR"
    report = {
        "gate": {"verdict": "error", "notices": []},
        "inputs": {
            "baseline_config": {"name": "baseline", "model": "m-base", "sha256": "b" * 64},
            "candidate_config": {"name": "candidate", "model": "m-cand", "sha256": "c" * 64},
            "dataset": {
                "name": "mini-golden",
                "version": "1.0.0",
                "n_items": 3,
                "task": "rag",
                "sha256": "d" * 64,
            },
            "scorer_config": {"sha256": "s" * 64},
            "thresholds": {"sha256": "t" * 64},
            "pricing_table": {"sha256": "", "version": "test-1"},
        },
        "runs": {
            "baseline": {"n_ok": 3, "n_items": 3, "n_errors": 0},
            "candidate": {"n_ok": 3, "n_items": 3, "n_errors": 0},
        },
        "rules": [{"metric": "quality.pass_rate", "verdict": "error"}],
        "metrics": {
            "quality.pass_rate": {
                "baseline": {"available": False, "value": None, "note": "no data"},
                "candidate": {"available": False, "value": None, "note": "no data"},
                "delta": None,
            },
        },
        "tool": {"name": "llm-release-gate", "version": "0.0-test"},
        "result_hash": "r" * 64,
    }
    md = render_markdown(report)
    assert md.splitlines()[0] == "## \u2753 llm-release-gate: **ERROR**"
    row = next(line for line in md.splitlines() if line.startswith("| quality.pass_rate |"))
    assert row.endswith("| \u2753 ERROR |")


def _reports(paths):
    report = json.loads(open(f"{paths['out']}/report.json", encoding="utf-8").read())
    md = open(f"{paths['out']}/report.md", encoding="utf-8").read()
    html = open(f"{paths['out']}/report.html", encoding="utf-8").read()
    return report, md, html


def test_markdown_shows_counts_heuristic_label_and_identity(mini_gate):
    paths = mini_gate()
    assert main(gate_argv(paths)) == 0
    report, md, html = _reports(paths)
    assert "PASS" in md
    assert "2/2 (100.0%)" in md            # quality rate with sample counts
    assert "quality.pass_rate †" in md     # heuristic marker
    assert "not a probability" in md       # heuristic footnote
    assert report["inputs"]["dataset"]["sha256"] in md
    assert report["result_hash"] in md
    assert "baseline answered 3/3 items" in md


def test_unavailable_cost_is_labeled_not_zero(mini_gate):
    paths = mini_gate(include_pricing=False)
    assert main(gate_argv(paths)) == 0
    report, md, html = _reports(paths)
    cost = report["metrics"]["cost.total_usd"]["candidate"]
    assert cost["available"] is False and cost["value"] is None
    assert "unavailable (no cost for 3 of 3 answered items: no pricing table supplied)" in md
    assert "$0" not in md                  # no fabricated cost anywhere
    assert "no pricing table supplied" in html


def test_markdown_surfaces_partial_coverage_note(mini_gate):
    # Candidate reports latency for only 1 of 3 answered items -> the runner marks
    # latency.p95 AVAILABLE with a coverage note. The markdown PR comment must show
    # that note (as the HTML already does) so a subset percentile is never read as a
    # full-run value with a misleading delta.
    partial = {k: dict(v) for k, v in GOOD_RESPONSE.items()}
    partial["r2"].pop("latency_ms")
    partial["r3"].pop("latency_ms")
    paths = mini_gate(candidate_responses=partial)
    assert main(gate_argv(paths)) == 0
    report, md, html = _reports(paths)
    note = report["metrics"]["latency.p95_ms"]["candidate"]["note"]
    assert note == "latency reported for 1 of 3 answered items"
    assert note in md
    assert note in html  # both renderers agree; the caveat is not dropped in either


def test_html_escapes_model_output(mini_gate):
    hostile = {k: dict(v) for k, v in GOOD_RESPONSE.items()}
    hostile["r1"]["text"] = 'The sky is blue <script>alert("x")</script> [doc:s1]'
    paths = mini_gate(candidate_responses=hostile)
    assert main(gate_argv(paths)) == 0
    _, _, html = _reports(paths)
    assert "<script>alert" not in html
    assert "&lt;script&gt;" in html


def test_failed_items_show_detail_in_reports(mini_gate):
    bad = {k: dict(v) for k, v in GOOD_RESPONSE.items()}
    bad["r2"]["text"] = "The capital is Freedonia City. [doc:s1]"
    paths = mini_gate(candidate_responses=bad)
    assert main(gate_argv(paths)) == 1
    report, md, html = _reports(paths)
    assert report["gate"]["verdict"] == "fail"
    assert "quality.pass_rate" in md and "drop 0.5" in md
    item = next(i for i in report["items"] if i["id"] == "r2")
    detail = item["candidate"]["scores"]["quality.pass_rate"]["detail"]
    assert "fredville" in detail
    assert "missing expected terms" in html


def test_markdown_breached_section_pins_heading_and_implicit(mini_gate):
    bad = {k: dict(v) for k, v in GOOD_RESPONSE.items()}
    bad["r2"]["text"] = "The capital is Freedonia City. [doc:s1]"
    paths = mini_gate(candidate_responses=bad)
    assert main(gate_argv(paths)) == 1
    report, md, _ = _reports(paths)
    assert report["gate"]["verdict"] == "fail"
    failing = next(
        r for r in report["rules"]
        if r["metric"] == "quality.pass_rate" and r["verdict"] == "fail"
    )
    assert "drop 0.5" in failing["message"]
    assert "### Breached thresholds" in md
    breached = md.split("### Breached thresholds")[1]
    if "### Metrics" in breached:
        breached = breached.split("### Metrics")[0]
    assert "- ❌ **quality.pass_rate**:" in breached
    breached_line = next(
        line for line in breached.splitlines()
        if "- ❌ **quality.pass_rate**:" in line
    )
    assert "drop 0.5" in breached_line
    # The default-thresholds failing rule is explicit, so pin the implicit
    # marker by re-rendering the same report with that rule marked implicit.
    import copy

    implicit_report = copy.deepcopy(report)
    for rule in implicit_report["rules"]:
        if rule["metric"] == "quality.pass_rate" and rule["verdict"] == "fail":
            rule["implicit"] = True
    implicit_md = render_markdown(implicit_report)
    implicit_breached = implicit_md.split("### Breached thresholds")[1]
    if "### Metrics" in implicit_breached:
        implicit_breached = implicit_breached.split("### Metrics")[0]
    assert "- ❌ **quality.pass_rate**:" in implicit_breached
    assert "*(implicit default rule)*" in implicit_breached


def test_percentile_nearest_rank_ceil():
    # Nearest-rank: rank = ceil(p/100 * n), 1-indexed; ceil, not floor/round.
    assert percentile([10, 20, 30, 40, 100], 95) == 100  # ceil(4.75) = 5th
    assert percentile([1, 2, 3, 4], 25) == 1  # ceil(1.0) = 1st
    assert percentile([10, 20, 30, 40, 50], 50) == 30  # ceil(2.5) = 3rd (median)
    assert percentile([10, 20, 30, 40, 50], 100) == 50  # ceil(5.0) = 5th (edge)
    with pytest.raises(ValueError):
        percentile([], 95)


def test_rate_metric_empty_cohort_is_unavailable():
    # Zero-denominator branch must stay unavailable (never 0.0 or "0/0").
    m = rate_metric(0, 0, "higher_better")
    assert m["value"] is None
    assert m["available"] is False
    assert m["numerator"] is None
    assert m["denominator"] is None
    assert m["n"] is None
    assert m["note"] == "no applicable items"

    # Negative/zero denominator variant stays unavailable as well.
    m_neg = rate_metric(0, -1, "higher_better")
    assert m_neg["value"] is None
    assert m_neg["available"] is False
    assert m_neg["numerator"] is None
    assert m_neg["denominator"] is None
    assert m_neg["n"] is None
    assert m_neg["note"] == "no applicable items"


def test_markdown_breached_section_filters_and_marks_implicit():
    from llm_release_gate.reports.markdown import render_markdown

    def _unavailable(note):
        return {"available": False, "value": None, "note": note}

    report = {
        "gate": {"verdict": "fail", "notices": []},
        "inputs": {
            "baseline_config": {"name": "baseline", "model": "model-b", "sha256": "b" * 64},
            "candidate_config": {"name": "candidate", "model": "model-c", "sha256": "c" * 64},
            "dataset": {
                "name": "ds", "version": "1", "n_items": 3, "task": "rag", "sha256": "d" * 64,
            },
            "scorer_config": {"sha256": "s" * 64},
            "thresholds": {"sha256": "t" * 64},
            "pricing_table": {"version": "1", "sha256": ""},
        },
        "runs": {
            "baseline": {"n_ok": 3, "n_items": 3, "n_errors": 0},
            "candidate": {"n_ok": 3, "n_items": 3, "n_errors": 0},
        },
        "rules": [
            {"metric": "cost.total_usd", "verdict": "pass", "message": "cost ok", "implicit": False},
            {
                "metric": "quality.pass_rate", "verdict": "fail",
                "message": "drop 0.5 below threshold", "implicit": True,
            },
            {
                "metric": "latency.p95_ms", "verdict": "warn",
                "message": "latency near threshold", "implicit": False,
            },
        ],
        "metrics": {
            key: {"baseline": _unavailable(note), "candidate": _unavailable(note), "delta": None}
            for key, note in (
                ("cost.total_usd", "no pricing"),
                ("quality.pass_rate", "no data"),
                ("latency.p95_ms", "no data"),
            )
        },
        "tool": {"name": "llm-release-gate", "version": "0.0-test"},
        "result_hash": "abc123",
    }
    md = render_markdown(report)
    assert "### Breached thresholds" in md
    breached = md.split("### Breached thresholds")[1].split("### Metrics")[0]
    assert "- ❌ **quality.pass_rate**: drop 0.5 below threshold *(implicit default rule)*" in breached
    assert "⚠️ **latency.p95_ms**" in breached
    assert "latency near threshold" in breached
    assert "cost.total_usd" not in breached


def test_zero_applicable_rate_stays_unavailable():
    m = rate_metric(0, 0, "higher_better")
    assert m["value"] is None
    assert m["available"] is False
    assert m["numerator"] is None
    assert m["denominator"] is None
    assert m["n"] is None
    assert m["note"] == "no applicable items"


def test_rate_metric_unavailable_keeps_custom_note():
    m = rate_metric(0, 0, "higher_better", note="why")
    assert m["value"] is None
    assert m["available"] is False
    assert m["note"] == "why"


def _minimal_markdown_report(notices):
    return {
        "gate": {"verdict": "pass", "notices": list(notices)},
        "inputs": {
            "baseline_config": {"name": "baseline", "model": "m-base", "sha256": "b" * 64},
            "candidate_config": {"name": "candidate", "model": "m-cand", "sha256": "c" * 64},
            "dataset": {
                "name": "mini-golden",
                "version": "1.0.0",
                "n_items": 3,
                "task": "rag",
                "sha256": "d" * 64,
            },
            "scorer_config": {"sha256": "s" * 64},
            "thresholds": {"sha256": "t" * 64},
            "pricing_table": {"sha256": "", "version": "test-1"},
        },
        "runs": {
            "baseline": {"n_ok": 3, "n_items": 3, "n_errors": 0},
            "candidate": {"n_ok": 3, "n_items": 3, "n_errors": 0},
        },
        "rules": [],
        "metrics": {},
        "tool": {"name": "llm-release-gate", "version": "0.0-test"},
        "result_hash": "r" * 64,
    }


def test_markdown_renders_gate_notices():
    notice = "candidate had provider errors on 2 items"
    md = render_markdown(_minimal_markdown_report([notice]))
    assert f"> \u26a0\ufe0f {notice}" in md

    md_empty = render_markdown(_minimal_markdown_report([]))
    assert not any(line.startswith(">") for line in md_empty.splitlines())


def test_markdown_formats_available_cost_and_latency(mini_gate):
    paths = mini_gate()
    assert main(gate_argv(paths)) == 0
    report, md, _ = _reports(paths)
    cost = report["metrics"]["cost.total_usd"]["baseline"]
    assert cost["available"] is True and cost["value"] is not None
    cost_row = next(line for line in md.splitlines() if line.startswith("| cost.total_usd |"))
    assert "| $0.004140" in cost_row
    latency = report["metrics"]["latency.p50_ms"]["baseline"]
    assert latency["available"] is True and latency["value"] is not None
    latency_row = next(line for line in md.splitlines() if line.startswith("| latency.p50_ms |"))
    assert "| 500 ms" in latency_row


def test_fmt_delta_shapes():
    """Pin fmt_delta strings: em dash for None, pp for rates, parens pct."""
    from llm_release_gate.reports import fmt_delta

    def entry(unit, abs_val, pct):
        return {
            "candidate": {"unit": unit},
            "delta": None if abs_val is None else {"abs": abs_val, "pct": pct},
        }

    # delta None -> em dash (U+2014); pct ignored.
    assert fmt_delta(entry("rate", None, None)) == "—"
    assert fmt_delta(entry("usd", None, None)) == "—"

    # Rates use a 'pp' suffix (never '%'); the pct argument is ignored.
    assert fmt_delta(entry("rate", -0.005, None)) == "-0.5pp"
    assert fmt_delta(entry("rate", 0.0125, 10)) == "+1.2pp"

    # Non-rates with pct use the 'abs (+x.x%)' parenthesized form.
    assert fmt_delta(entry("usd", 0.001, 12.5)) == "+0.001000 (+12.5%)"
    assert fmt_delta(entry("tokens", -2000.0, -10.0)) == "-2,000 (-10.0%)"

    # Non-rates with pct None render abs only (no parens, no percent).
    assert fmt_delta(entry("tokens", 3.0, None)) == "+3"
    assert fmt_delta(entry("tokens", -4.0, None)) == "-4"


def test_markdown_and_html_render_deltas():
    """Markdown/HTML delta cells embed the exact fmt_delta strings."""
    from llm_release_gate.reports import fmt_delta
    from llm_release_gate.reports.html import render_html

    def avail(unit, value, **extra):
        metric = {
            "available": True,
            "value": value,
            "unit": unit,
            "numerator": None,
            "denominator": None,
            "n": None,
            "note": None,
        }
        metric.update(extra)
        return metric

    rate_entry = {
        "baseline": avail("rate", 0.5, numerator=1, denominator=2),
        "candidate": avail("rate", 0.495, numerator=1, denominator=2),
        "delta": {"abs": -0.005, "pct": 3.0},
    }
    cost_entry = {
        "baseline": avail("usd", 0.004),
        "candidate": avail("usd", 0.003),
        "delta": {"abs": -0.001, "pct": -10.0},
    }
    report = _minimal_markdown_report([])
    report["metrics"] = {
        "quality.pass_rate": rate_entry,
        "cost.total_usd": cost_entry,
    }
    report["items"] = []

    rate_expected = fmt_delta(rate_entry)
    cost_expected = fmt_delta(cost_entry)
    assert rate_expected == "-0.5pp"
    assert cost_expected == "-0.001000 (-10.0%)"

    md = render_markdown(report)
    rate_row = next(
        line for line in md.splitlines() if line.startswith("| quality.pass_rate |")
    )
    cost_row = next(
        line for line in md.splitlines() if line.startswith("| cost.total_usd |")
    )
    assert rate_expected in rate_row
    assert rate_row.split("|")[4].strip() == rate_expected
    assert rate_expected.endswith("pp")
    assert "%" not in rate_expected
    assert cost_expected in cost_row
    assert cost_row.split("|")[4].strip() == cost_expected
    assert "(+" in cost_expected or "(-" in cost_expected
    assert cost_expected.endswith("%)")

    html_doc = render_html(report)
    assert rate_expected in html_doc
    assert cost_expected in html_doc


def test_html_item_cells_for_na_error_and_abstain():
    import html as _html

    from llm_release_gate.reports.html import render_html

    hostile = 'boom <b>down</b> & <script>alert("e")</script>'
    abstained_pass = {
        "status": "ok",
        "error": None,
        "text": None,
        "abstained": True,
        "scores": {
            "quality.pass_rate": {"applicable": True, "passed": True, "detail": None},
        },
    }
    report = _minimal_markdown_report([])
    report["items"] = [
        {
            "id": "r1",
            "baseline": None,
            "candidate": {"status": "error", "error": hostile},
        },
        {
            "id": "r2",
            "baseline": {
                "status": "ok",
                "error": None,
                "text": None,
                "abstained": False,
                "scores": {
                    "quality.pass_rate": {
                        "applicable": True,
                        "passed": True,
                        "detail": None,
                    },
                },
            },
            "candidate": abstained_pass,
        },
    ]

    out = render_html(report)

    assert '<span class="badge na">N/A</span>' in out
    assert '<span class="badge error">ERROR</span>' in out
    assert _html.escape(hostile) in out  # escaped error text
    assert hostile not in out
    assert '<span class="note">abstained</span>' in out  # abstained branch

    assert out.count('<span class="badge na">N/A</span>') == 1
