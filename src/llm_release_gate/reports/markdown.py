"""Markdown report — written as report.md and used verbatim as the PR comment
and the GitHub step summary. Concise on purpose: verdict first, breached rules
next, full metric table after, identity block last."""

from __future__ import annotations

import html
import re

from . import HEURISTIC_FOOTNOTE, fmt_delta, fmt_value, is_heuristic, verdict_word

_VERDICT_ICON = {"pass": "✅", "fail": "❌", "warn": "⚠️", "skipped": "⏭️"}


def _escape_cell(text: str) -> str:
    text = html.escape(str(text), quote=False)
    text = re.sub(r"[\\`*\[\]{}#!|]|(?<!\w)_|_(?!\w)", lambda m: f"&#{ord(m[0])};", text)
    return (text.replace("@", "@\u200b").replace("\r\n", "<br/>")
            .replace("\n", "<br/>").replace("\r", "<br/>"))


def render_markdown(report: dict) -> str:
    gate = report["gate"]
    inputs = report["inputs"]
    runs = report["runs"]
    icon = _VERDICT_ICON.get(gate["verdict"], "❓")
    lines: list[str] = []
    heuristic_used = False

    lines.append(f"## {icon} llm-release-gate: **{verdict_word(gate['verdict'])}**")
    lines.append("")
    lines.append(
        f"<code>{_escape_cell(inputs['baseline_config']['name'])}</code> ({_escape_cell(inputs['baseline_config']['model'])}) vs "
        f"<code>{_escape_cell(inputs['candidate_config']['name'])}</code> ({_escape_cell(inputs['candidate_config']['model'])}) "
        f"on dataset **{_escape_cell(inputs['dataset']['name'])}** v{_escape_cell(inputs['dataset']['version'])} "
        f"({inputs['dataset']['n_items']} items, task: {inputs['dataset']['task']})"
    )
    lines.append("")

    breached = [r for r in report["rules"] if r["verdict"] in ("fail", "warn")]
    if breached:
        lines.append("### Breached thresholds")
        lines.append("")
        for rule in breached:
            rule_icon = _VERDICT_ICON[rule["verdict"]]
            implicit = " *(implicit default rule)*" if rule["implicit"] else ""
            lines.append(f"- {rule_icon} **{_escape_cell(rule['metric'])}**: {_escape_cell(rule['message'])}{implicit}")
        lines.append("")

    for notice in gate["notices"]:
        lines.append(f"> ⚠️ {_escape_cell(notice)}")
    if gate["notices"]:
        lines.append("")

    lines.append("### Metrics")
    lines.append("")
    lines.append("| Metric | Baseline | Candidate | Δ (candidate−baseline) | Gate |")
    lines.append("|---|---|---|---|---|")
    rules_by_metric: dict[str, list[dict]] = {}
    for rule in report["rules"]:
        rules_by_metric.setdefault(rule["metric"], []).append(rule)
    for key, entry in report["metrics"].items():
        mark = ""
        if is_heuristic(entry["baseline"]) or is_heuristic(entry["candidate"]):
            mark = " †"
            heuristic_used = True
        cells = {}
        for side, m in (("b", entry["baseline"]), ("c", entry["candidate"])):
            if not m["available"] and m["note"]:
                cells[side] = f"unavailable ({m['note']})"
            elif m["note"]:
                # An AVAILABLE metric can still carry a caveat (partial-coverage
                # latency, cost/token basis). Surface it — matching the HTML report —
                # so a subset percentile is never shown as a bare full-run value.
                cells[side] = f"{fmt_value(m)} ({m['note']})"
            else:
                cells[side] = fmt_value(m)
        b_txt, c_txt = _escape_cell(cells["b"]), _escape_cell(cells["c"])
        gate_cells = [
            f"{_VERDICT_ICON.get(r['verdict'], '❓')} {verdict_word(r['verdict'])}"
            for r in rules_by_metric.get(key, [])
        ]
        gate_cell = _escape_cell(", ".join(gate_cells) if gate_cells else "—")
        delta_txt = _escape_cell(fmt_delta(entry))
        lines.append(f"| {_escape_cell(key)}{mark} | {b_txt} | {c_txt} | {delta_txt} | {gate_cell} |")
    lines.append("")
    if heuristic_used:
        lines.append(f"† {HEURISTIC_FOOTNOTE}.")
        lines.append("")

    b, c = runs["baseline"], runs["candidate"]
    b_errors = "item-processing errors" if b.get("n_processing_errors") else "provider errors"
    c_errors = "item-processing errors" if c.get("n_processing_errors") else "provider errors"
    lines.append(
        f"Samples: baseline answered {b['n_ok']}/{b['n_items']} items "
        f"({b['n_errors']} {b_errors}); candidate answered {c['n_ok']}/{c['n_items']} "
        f"({c['n_errors']} {c_errors}). Rates are computed over applicable, "
        f"answered items only — see per-metric counts above."
    )
    lines.append("")
    lines.append("<details><summary>Run identity</summary>")
    lines.append("")
    lines.append(f"- tool: {report['tool']['name']} v{report['tool']['version']}")
    lines.append(f"- dataset: `{inputs['dataset']['sha256']}`")
    lines.append(f"- baseline config: `{inputs['baseline_config']['sha256']}`")
    lines.append(f"- candidate config: `{inputs['candidate_config']['sha256']}`")
    lines.append(f"- scorers: `{inputs['scorer_config']['sha256']}`")
    lines.append(f"- thresholds: `{inputs['thresholds']['sha256']}`")
    pricing = inputs["pricing_table"]
    if pricing["sha256"]:
        lines.append(f"- pricing table: v{_escape_cell(pricing['version'])} `{pricing['sha256']}`")
    else:
        lines.append("- pricing table: none supplied (cost reported unavailable)")
    lines.append(f"- result: `{report['result_hash']}`")
    lines.append("")
    lines.append("</details>")
    lines.append("")
    return "\n".join(lines)
