"""Standalone HTML report: everything in the Markdown summary plus per-item
drill-down. Self-contained (inline CSS, no external assets) so it can be
attached as a CI artifact and opened anywhere."""

from __future__ import annotations

import html

from . import HEURISTIC_FOOTNOTE, fmt_delta, fmt_value, is_heuristic, verdict_word

_CSS = """
body { font-family: -apple-system, "Segoe UI", Roboto, sans-serif; margin: 2rem auto;
       max-width: 70rem; padding: 0 1rem; color: #1f2328; }
h1 { font-size: 1.4rem; } h2 { font-size: 1.1rem; margin-top: 2rem; }
table { border-collapse: collapse; width: 100%; margin: 0.5rem 0 1rem; font-size: 0.9rem; }
th, td { border: 1px solid #d1d9e0; padding: 0.4rem 0.6rem; text-align: left;
         vertical-align: top; }
th { background: #f6f8fa; }
.verdict { display: inline-block; padding: 0.2rem 0.8rem; border-radius: 0.4rem;
           font-weight: 700; color: #fff; }
.verdict.pass { background: #1a7f37; } .verdict.fail { background: #cf222e; }
.badge { display: inline-block; padding: 0 0.45rem; border-radius: 0.6rem;
         font-size: 0.8rem; font-weight: 600; }
.badge.pass { background: #dafbe1; color: #1a7f37; }
.badge.fail { background: #ffebe9; color: #cf222e; }
.badge.warn { background: #fff8c5; color: #7d4e00; }
.badge.skipped, .badge.na { background: #eaeef2; color: #57606a; }
.badge.error { background: #ffebe9; color: #cf222e; }
.note { color: #57606a; font-size: 0.85rem; }
code { background: #f6f8fa; padding: 0.1rem 0.3rem; border-radius: 0.3rem;
       font-size: 0.85em; word-break: break-all; }
details > summary { cursor: pointer; }
pre { background: #f6f8fa; padding: 0.6rem; border-radius: 0.4rem;
      white-space: pre-wrap; font-size: 0.85rem; }
"""


def _esc(value) -> str:
    return html.escape(str(value))


def _badge(verdict: str) -> str:
    return f'<span class="badge {_esc(verdict)}">{_esc(verdict_word(verdict))}</span>'


def _item_cell(record: dict | None) -> str:
    if record is None:
        return '<span class="badge na">N/A</span>'
    if record["status"] == "error":
        return f'<span class="badge error">ERROR</span> <span class="note">{_esc(record["error"])}</span>'
    parts = []
    failed = [
        f"{key}: {res['detail'] or 'failed'}"
        for key, res in record["scores"].items()
        if res["applicable"] and res["passed"] is False
    ]
    parts.append(_badge("fail") if failed else _badge("pass"))
    if record["abstained"]:
        parts.append('<span class="note">abstained</span>')
    if failed:
        parts.append(f'<div class="note">{_esc("; ".join(failed))}</div>')
    text = record.get("text")
    if text:
        parts.append(
            f"<details><summary class=\"note\">output</summary><pre>{_esc(text)}</pre></details>"
        )
    return " ".join(parts)


def render_html(report: dict) -> str:
    gate = report["gate"]
    inputs = report["inputs"]
    out: list[str] = []
    out.append("<!DOCTYPE html><html lang=\"en\"><head><meta charset=\"utf-8\">")
    out.append(f"<title>llm-release-gate: {_esc(verdict_word(gate['verdict']))}</title>")
    out.append(f"<style>{_CSS}</style></head><body>")

    out.append(
        f"<h1>llm-release-gate "
        f"<span class=\"verdict {_esc(gate['verdict'])}\">{_esc(verdict_word(gate['verdict']))}</span></h1>"
    )
    out.append(
        f"<p><strong>{_esc(inputs['baseline_config']['name'])}</strong> "
        f"({_esc(inputs['baseline_config']['model'])}) vs "
        f"<strong>{_esc(inputs['candidate_config']['name'])}</strong> "
        f"({_esc(inputs['candidate_config']['model'])}) on dataset "
        f"<strong>{_esc(inputs['dataset']['name'])}</strong> v{_esc(inputs['dataset']['version'])} "
        f"({inputs['dataset']['n_items']} items, task: {_esc(inputs['dataset']['task'])})</p>"
    )
    for notice in gate["notices"]:
        out.append(f"<p class=\"note\">⚠️ {_esc(notice)}</p>")

    out.append("<h2>Threshold rules</h2><table>")
    out.append(
        "<tr><th>Metric</th><th>Constraints</th><th>Level</th>"
        "<th>Result</th><th>Detail</th></tr>"
    )
    for rule in report["rules"]:
        constraints = ", ".join(f"{k}={v}" for k, v in
                                ((c["constraint"], c["threshold"]) for c in rule["checks"]))
        implicit = " <span class=\"note\">(implicit default)</span>" if rule["implicit"] else ""
        out.append(
            f"<tr><td>{_esc(rule['metric'])}{implicit}</td><td>{_esc(constraints)}</td>"
            f"<td>{_esc(rule['level'])}</td><td>{_badge(rule['verdict'])}</td>"
            f"<td>{_esc(rule['message'])}</td></tr>"
        )
    out.append("</table>")

    heuristic_used = False
    out.append("<h2>Metrics</h2><table>")
    out.append(
        "<tr><th>Metric</th><th>Baseline</th><th>Candidate</th>"
        "<th>&Delta; (candidate&minus;baseline)</th></tr>"
    )
    for key, entry in report["metrics"].items():
        mark = ""
        if is_heuristic(entry["baseline"]) or is_heuristic(entry["candidate"]):
            mark = " †"
            heuristic_used = True
        cells = []
        for m in (entry["baseline"], entry["candidate"]):
            txt = fmt_value(m)
            if not m["available"] and m["note"]:
                txt = f"unavailable <span class=\"note\">({_esc(m['note'])})</span>"
            else:
                txt = _esc(txt)
                if m["note"]:
                    txt += f" <span class=\"note\">({_esc(m['note'])})</span>"
            cells.append(txt)
        out.append(
            f"<tr><td>{_esc(key)}{mark}</td><td>{cells[0]}</td><td>{cells[1]}</td>"
            f"<td>{_esc(fmt_delta(entry))}</td></tr>"
        )
    out.append("</table>")
    if heuristic_used:
        out.append(f"<p class=\"note\">† {_esc(HEURISTIC_FOOTNOTE)}.</p>")

    runs = report["runs"]
    b, c = runs["baseline"], runs["candidate"]
    b_errors = "item-processing errors" if b.get("n_processing_errors") else "provider errors"
    c_errors = "item-processing errors" if c.get("n_processing_errors") else "provider errors"
    out.append(
        f"<p class=\"note\">Samples: baseline answered {b['n_ok']}/{b['n_items']} items "
        f"({b['n_errors']} {b_errors}); candidate answered {c['n_ok']}/{c['n_items']} "
        f"({c['n_errors']} {c_errors}).</p>"
    )

    out.append("<h2>Items</h2><table>")
    out.append("<tr><th>Item</th><th>Baseline</th><th>Candidate</th></tr>")
    for item in report["items"]:
        out.append(
            f"<tr><td><code>{_esc(item['id'])}</code></td>"
            f"<td>{_item_cell(item['baseline'])}</td>"
            f"<td>{_item_cell(item['candidate'])}</td></tr>"
        )
    out.append("</table>")

    out.append("<h2>Run identity</h2><table>")
    rows = [
        ("tool", f"{report['tool']['name']} v{report['tool']['version']}"),
        ("dataset", inputs["dataset"]["sha256"]),
        ("baseline config", inputs["baseline_config"]["sha256"]),
        ("candidate config", inputs["candidate_config"]["sha256"]),
        ("scorer config", inputs["scorer_config"]["sha256"]),
        ("thresholds", inputs["thresholds"]["sha256"]),
        (
            "pricing table",
            f"v{inputs['pricing_table']['version']} {inputs['pricing_table']['sha256']}"
            if inputs["pricing_table"]["sha256"]
            else "none supplied (cost reported unavailable)",
        ),
        ("result hash", report["result_hash"]),
    ]
    for label, value in rows:
        out.append(f"<tr><th>{_esc(label)}</th><td><code>{_esc(value)}</code></td></tr>")
    out.append("</table>")

    out.append("</body></html>")
    return "".join(out)
