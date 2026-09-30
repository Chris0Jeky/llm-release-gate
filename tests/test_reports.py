"""Report generation: sample counts shown, heuristics labeled, HTML escaped,
unavailable values explained."""

import json

from llm_release_gate.cli import main

from llm_release_gate.metrics import rate_metric
from conftest import GOOD_RESPONSE, gate_argv


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
