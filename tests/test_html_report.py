"""HTML report regression pins: per-item cells and escaping of non-model text.

Direct unit tests over ``llm_release_gate.reports.html.render_html`` with
hand-built report dicts: deterministic (no clock, network, or filesystem).
"""

from __future__ import annotations

import html as _html

from llm_release_gate.reports.html import render_html

HOSTILE = '<script>alert("x")</script> & stuff'


def _metric_value(available=True, note="", unit="rate", numerator=2,
                  denominator=2, value=1.0, kind="rate"):
    entry = {
        "available": available,
        "note": note,
        "unit": unit,
        "numerator": numerator,
        "denominator": denominator,
        "value": value,
        "kind": kind,
    }
    return entry


def _ok_record(text=None, abstained=False, scores=None):
    if scores is None:
        scores = {"quality.pass_rate": {"applicable": True, "passed": True, "detail": None}}
    return {"status": "ok", "error": None, "text": text,
            "abstained": abstained, "scores": scores}


def _base_report(**overrides):
    report = {
        "gate": {"verdict": "pass", "notices": []},
        "inputs": {
            "baseline_config": {"name": "baseline", "model": "m-base", "sha256": "bsha"},
            "candidate_config": {"name": "candidate", "model": "m-cand", "sha256": "csha"},
            "dataset": {"name": "mini-golden", "version": "1.0.0", "n_items": 3,
                        "task": "rag", "sha256": "dsha"},
            "scorer_config": {"sha256": "ssha"},
            "thresholds": {"sha256": "tsha"},
            "pricing_table": {"version": "test-1", "sha256": None},
        },
        "rules": [
            {"metric": "quality.pass_rate",
             "checks": [{"constraint": "max_drop_abs", "threshold": 0.0}],
             "implicit": False, "level": "gate", "verdict": "pass", "message": "ok"},
        ],
        "metrics": {
            "quality.pass_rate": {
                "baseline": _metric_value(),
                "candidate": _metric_value(),
                "delta": None,
            },
        },
        "runs": {
            "baseline": {"n_ok": 3, "n_items": 3, "n_errors": 0},
            "candidate": {"n_ok": 3, "n_items": 3, "n_errors": 0},
        },
        "items": [
            {"id": "r1", "baseline": _ok_record(), "candidate": _ok_record()},
        ],
        "tool": {"name": "llm-release-gate", "version": "0.0-test"},
        "result_hash": "deadbeef",
    }
    report.update(overrides)
    return report


def _item_cells(out: str, item_id: str) -> list[str]:
    """The Baseline and Candidate <td> contents of one Items-table row.

    Scoping assertions to the row keeps the rules table's own verdict badges
    (Codex review of #27) from satisfying an item-cell assertion.
    """
    row = out[out.index(f"<tr><td><code>{item_id}</code></td>"):]
    row = row[:row.index("</tr>")]
    cells = row.split("<td>")[2:]
    return [cell[: cell.rindex("</td>")] for cell in cells]


# --- per-item cell: missing record (N/A) ---

def test_missing_baseline_record_renders_na_badge():
    report = _base_report(items=[
        {"id": "r1", "baseline": None, "candidate": _ok_record()},
    ])
    out = render_html(report)
    baseline, candidate = _item_cells(out, "r1")
    assert baseline == '<span class="badge na">N/A</span>'
    assert candidate == '<span class="badge pass">PASS</span>'
    assert out.count('<span class="badge na">N/A</span>') == 1


def test_empty_items_table_renders_no_na_badge():
    report = _base_report(items=[])
    out = render_html(report)
    assert "<h2>Items</h2><table>" in out
    assert '<span class="badge na">N/A</span>' not in out
    assert "<code>r1</code>" not in out


# --- per-item cell: provider error ---

def test_provider_error_renders_error_badge_with_escaped_message():
    msg = 'boom <script>alert("e")</script> & down'
    report = _base_report(items=[
        {"id": "r1",
         "baseline": {"status": "error", "error": msg},
         "candidate": _ok_record()},
    ])
    out = render_html(report)
    baseline, _ = _item_cells(out, "r1")
    assert baseline.startswith('<span class="badge error">ERROR</span>')
    assert _html.escape(msg) in baseline
    assert msg not in out
    assert "<script>" not in out


def test_provider_error_with_empty_message_still_renders_error_badge():
    report = _base_report(items=[
        {"id": "r1",
         "baseline": {"status": "error", "error": ""},
         "candidate": _ok_record()},
    ])
    out = render_html(report)
    assert '<span class="badge error">ERROR</span> <span class="note"></span>' in out


# --- per-item cell: abstained item ---

def test_abstained_item_shows_pass_badge_and_abstained_note():
    record = _ok_record(abstained=True, scores={
        "quality.pass_rate": {"applicable": False, "passed": None, "detail": None},
    })
    report = _base_report(items=[{"id": "r3", "baseline": record, "candidate": record}])
    out = render_html(report)
    for cell in _item_cells(out, "r3"):
        assert cell.startswith('<span class="badge pass">PASS</span>')
        assert '<span class="note">abstained</span>' in cell


def test_non_abstained_item_shows_no_abstained_note():
    record = _ok_record(abstained=False)
    report = _base_report(items=[{"id": "r1", "baseline": record, "candidate": record}])
    out = render_html(report)
    for cell in _item_cells(out, "r1"):
        assert cell == '<span class="badge pass">PASS</span>'
    assert '<span class="note">abstained</span>' not in out


# --- per-item cell: failed item with no detail ---

def test_failed_item_without_detail_falls_back_to_failed_word():
    record = _ok_record(scores={
        "quality.pass_rate": {"applicable": True, "passed": False, "detail": None},
    })
    report = _base_report(items=[{"id": "r2", "baseline": _ok_record(), "candidate": record}])
    out = render_html(report)
    _, candidate = _item_cells(out, "r2")
    assert candidate.startswith('<span class="badge fail">FAIL</span>')
    assert '<div class="note">quality.pass_rate: failed</div>' in candidate


def test_inapplicable_score_does_not_render_as_failure():
    record = _ok_record(scores={
        "quality.pass_rate": {"applicable": False, "passed": False, "detail": None},
    })
    report = _base_report(items=[{"id": "r2", "baseline": _ok_record(), "candidate": record}])
    out = render_html(report)
    _, candidate = _item_cells(out, "r2")
    assert candidate == '<span class="badge pass">PASS</span>'
    assert "quality.pass_rate: failed" not in out
    assert '<span class="badge fail">FAIL</span>' not in out


# --- escaping: gate notices ---

def test_gate_notice_is_escaped():
    notice = f"coverage <script>alert(1)</script> & {HOSTILE}"
    report = _base_report(gate={"verdict": "pass", "notices": [notice]})
    out = render_html(report)
    assert _html.escape(notice) in out
    assert notice not in out
    assert "<script>" not in out


def test_empty_gate_notice_renders_without_raw_markup():
    report = _base_report(gate={"verdict": "pass", "notices": [""]})
    out = render_html(report)
    assert '<p class="note">⚠️ </p>' in out
    assert "<script>" not in out


# --- escaping: config and dataset names ---

def test_config_and_dataset_names_are_escaped():
    base_name = "<script>base</script> & b"
    cand_name = "<script>cand</script> & c"
    ds_name = "<script>data</script> & d"
    report = _base_report()
    report["inputs"]["baseline_config"]["name"] = base_name
    report["inputs"]["candidate_config"]["name"] = cand_name
    report["inputs"]["dataset"]["name"] = ds_name
    out = render_html(report)
    for raw in (base_name, cand_name, ds_name):
        assert _html.escape(raw) in out
        assert raw not in out
    assert "<script>" not in out


def test_empty_config_and_dataset_names_render_without_crash():
    report = _base_report()
    report["inputs"]["baseline_config"]["name"] = ""
    report["inputs"]["candidate_config"]["name"] = ""
    report["inputs"]["dataset"]["name"] = ""
    out = render_html(report)
    assert "<strong></strong>" in out
    assert "<script>" not in out


# --- escaping: rule messages ---

def test_rule_message_is_escaped():
    message = f"drop <script>alert(2)</script> & {HOSTILE}"
    report = _base_report()
    report["rules"][0]["message"] = message
    out = render_html(report)
    assert _html.escape(message) in out
    assert message not in out
    assert "<script>" not in out


def test_rule_with_no_checks_renders_empty_constraints_cell():
    report = _base_report()
    report["rules"][0]["checks"] = []
    report["rules"][0]["message"] = "ok"
    out = render_html(report)
    assert "<td></td>" in out
    assert "quality.pass_rate" in out


# --- escaping: metric notes ---

def test_unavailable_metric_note_is_escaped():
    note = f"no cost <script>alert(3)</script> & {HOSTILE}"
    report = _base_report()
    report["metrics"]["quality.pass_rate"]["baseline"] = _metric_value(
        available=False, note=note, value=None, numerator=0, denominator=0)
    out = render_html(report)
    assert f"unavailable <span class=\"note\">({_html.escape(note)})</span>" in out
    assert note not in out
    assert "<script>" not in out


def test_metric_without_note_renders_no_note_span():
    report = _base_report()
    out = render_html(report)
    assert "2/2 (100.0%)" in out
    assert '<span class="note">(' not in out
