"""Comparison + threshold verdicts. This is the logic CI trusts.

Semantics:
- A rule names one metric and one or more constraints. Constraints comparing
  candidate to baseline: max_drop_abs / max_drop_pct (for higher-is-better
  metrics), max_increase_abs / max_increase_pct (for lower-is-better metrics).
  Absolute floors/ceilings on the candidate alone: min_value / max_value.
- level "fail" breaks the gate; level "warn" only annotates the report.
- Unavailable data is handled fail-closed: if a rule's metric cannot be
  evaluated (missing tokens, model absent from the pricing table, no applicable
  items), the rule's on_unavailable policy applies — default "fail". A gate you
  cannot evaluate is not a passing gate.
- If no user rule covers errors.error_rate, an implicit fail rule
  (max_value: 0 on the candidate) is added: silent provider failures must
  never let a candidate pass on the strength of the items that succeeded.
- A rule naming a metric that no configured scorer emits is a configuration
  error (exit 2), not a passing check.
- A rule naming a metric present on only one side (asymmetric aggregates) is
  a configuration error (exit 2) naming the metric and which side is missing;
  partial aggregates are never silently treated as unavailable.
- A malformed aggregate entry (non-dict, or a dict missing its "available" /
  "value" keys, or marked available with a missing value) is a configuration
  error (exit 2), never a KeyError.
- Integer-only comparisons are exact, including percentage comparisons before
  division. Float comparisons allow EPS in the constraint's units (percentage
  points for percentages). Zero-baseline percentages have zero tolerance:
  signed zero is zero; any representable change in the guarded direction
  breaches a finite cap. A nonzero value cannot be inferred to be float noise.
"""

from __future__ import annotations

from . import REPORT_SCHEMA_VERSION, TOOL_NAME, __version__
from .errors import GateConfigError
from .hashing import content_hash
from .loading import (
    Dataset, PricingTable, RunConfig, ScorerConfig, ThresholdRule, Thresholds,
)
from .runner import ItemRecord, RunResult
from .requests import BINDING_SCHEME
from .policy_validation import require_number, validate_rule

EPS = 1e-9

_NEEDS_BASELINE = {"max_drop_abs", "max_drop_pct", "max_increase_abs", "max_increase_pct"}
_DROP_CONSTRAINTS = {"max_drop_abs", "max_drop_pct"}
_INCREASE_CONSTRAINTS = {"max_increase_abs", "max_increase_pct"}

_VERDICT_RANK = {"pass": 0, "skipped": 0, "warn": 1, "fail": 2}


def _escalate(current: str, new: str) -> str:
    return new if _VERDICT_RANK[new] > _VERDICT_RANK[current] else current


def _fmt(value: float | None) -> str:
    if value is None:
        return "n/a"
    try:
        return f"{value:.6g}"
    except OverflowError:
        return str(value)  # Preserve exact integers outside floating-point range.


def _exceeds(value: float, threshold: float) -> bool:
    if type(value) is int and type(threshold) is int:
        return value > threshold
    return value > threshold + EPS


def _percentage_change(delta: float, baseline: float, threshold: float) -> tuple[bool, float]:
    pct = delta / abs(baseline) * 100
    if all(type(value) is int for value in (delta, baseline, threshold)):
        # Cross-multiply before division can round away an integer violation.
        return delta * 100 > threshold * abs(baseline), pct
    return _exceeds(pct, threshold), pct


def _check_constraint(
    name: str, threshold: float, baseline: float | None, candidate: float
) -> tuple[bool, float | None, str]:
    """Return (breached, observed, message). baseline is None only for min/max_value."""
    if name == "max_drop_abs":
        drop = baseline - candidate
        return _exceeds(drop, threshold), drop, f"drop {_fmt(drop)} vs allowed {_fmt(threshold)}"
    if name == "max_drop_pct":
        if baseline == 0:
            breached = candidate < 0  # any drop from zero is an infinite percentage
            return breached, None, "baseline is 0; percentage drop undefined"
        breached, drop_pct = _percentage_change(baseline - candidate, baseline, threshold)
        return breached, drop_pct, (
            f"drop {_fmt(drop_pct)}% vs allowed {_fmt(threshold)}%"
        )
    if name == "max_increase_abs":
        inc = candidate - baseline
        return _exceeds(inc, threshold), inc, f"increase {_fmt(inc)} vs allowed {_fmt(threshold)}"
    if name == "max_increase_pct":
        if baseline == 0:
            breached = candidate > 0  # no absolute EPS allowance at a zero baseline
            return breached, None, (
                "baseline is 0; any increase breaches a percentage cap"
                if breached else (
                    "baseline and candidate both 0" if candidate == 0
                    else "baseline is 0; candidate decreased"
                )
            )
        breached, inc_pct = _percentage_change(candidate - baseline, baseline, threshold)
        return breached, inc_pct, (
            f"increase {_fmt(inc_pct)}% vs allowed {_fmt(threshold)}%"
        )
    if name == "min_value":
        return _exceeds(-candidate, -threshold), candidate, (
            f"candidate {_fmt(candidate)} vs required minimum {_fmt(threshold)}"
        )
    if name == "max_value":
        return _exceeds(candidate, threshold), candidate, (
            f"candidate {_fmt(candidate)} vs allowed maximum {_fmt(threshold)}"
        )
    raise GateConfigError(f"unknown constraint '{name}'")  # loading validates; belt+braces


def _require_aggregate(metric: dict, rule_metric: str, side: str) -> dict:
    if not isinstance(metric, dict):
        raise GateConfigError(
            f"aggregate for metric '{rule_metric}' on {side} side is malformed: "
            f"expected a metric dict, got {type(metric).__name__}"
        )
    if "available" not in metric:
        raise GateConfigError(
            f"aggregate for metric '{rule_metric}' on {side} side is malformed: "
            f"missing 'available' key"
        )
    if type(metric["available"]) is not bool:
        raise GateConfigError(f"aggregate for '{rule_metric}' on {side}: available must be boolean")
    return metric


def _aggregate_value(metric: dict, rule_metric: str, side: str):
    if "value" not in metric:
        raise GateConfigError(
            f"aggregate for metric '{rule_metric}' on {side} side is malformed: "
            f"missing 'value' key"
        )
    value = metric.get("value")
    if value is None:
        raise GateConfigError(
            f"aggregate for metric '{rule_metric}' on {side} side is malformed: "
            f"marked available but 'value' is None"
        )
    return require_number(value, f"aggregate for '{rule_metric}' on {side}")


def _evaluate_rule(
    rule: ThresholdRule, baseline_m: dict, candidate_m: dict, implicit: bool,
    comparison_issue: str | None = None,
) -> dict:
    checks = []
    verdict = "pass"
    any_evaluated = False
    _require_aggregate(candidate_m, rule.metric, "candidate")
    _require_aggregate(baseline_m, rule.metric, "baseline")
    for name, threshold in rule.constraints.items():
        needs_baseline = name in _NEEDS_BASELINE
        missing = []
        _require_aggregate(candidate_m, rule.metric, "candidate")
        _require_aggregate(baseline_m, rule.metric, "baseline")
        if not candidate_m.get("available"):
            missing.append(f"candidate: {candidate_m.get('note') or 'unavailable'}")
        if needs_baseline and not baseline_m.get("available"):
            missing.append(f"baseline: {baseline_m.get('note') or 'unavailable'}")
        if needs_baseline and comparison_issue:
            missing.append(comparison_issue)
        if missing:
            checks.append({
                "constraint": name,
                "threshold": threshold,
                "status": "unavailable",
                "observed": None,
                "message": "; ".join(missing) + f" — on_unavailable={rule.on_unavailable}",
            })
            if rule.on_unavailable == "fail":
                verdict = _escalate(verdict, "fail")
            elif rule.on_unavailable == "warn":
                verdict = _escalate(verdict, "warn")
            continue
        any_evaluated = True
        try:
            breached, observed, message = _check_constraint(
                name, threshold,
                _aggregate_value(baseline_m, rule.metric, "baseline") if needs_baseline else None,
                _aggregate_value(candidate_m, rule.metric, "candidate"),
            )
            if observed is not None:
                require_number(observed, f"threshold arithmetic for '{rule.metric}'")
        except ArithmeticError as exc:
            raise GateConfigError(f"threshold arithmetic for '{rule.metric}' cannot be represented") from exc
        checks.append({
            "constraint": name,
            "threshold": threshold,
            "status": "breached" if breached else "pass",
            "observed": observed,
            "message": message,
        })
        if breached:
            verdict = _escalate(verdict, rule.level)
    if not any_evaluated and rule.on_unavailable == "skip":
        verdict = "skipped"
    breached_msgs = [c["message"] for c in checks if c["status"] == "breached"]
    unavailable_msgs = [c["message"] for c in checks if c["status"] == "unavailable"]
    if breached_msgs:
        summary = "; ".join(breached_msgs)
    elif unavailable_msgs:
        summary = "; ".join(unavailable_msgs)
    else:
        summary = "within thresholds"
    return {
        "metric": rule.metric,
        "level": rule.level,
        "on_unavailable": rule.on_unavailable,
        "implicit": implicit,
        "verdict": verdict,
        "checks": checks,
        "message": summary,
        "baseline": baseline_m,
        "candidate": candidate_m,
    }


def evaluate_thresholds(
    thresholds: Thresholds, baseline_aggs: dict, candidate_aggs: dict,
    comparison_issues: dict[str, str] | None = None,
) -> list[dict]:
    known = set(baseline_aggs) | set(candidate_aggs)
    rules = list(thresholds.rules)
    for rule in rules:
        validate_rule(rule)
    implicit_flags = [False] * len(rules)
    if not any(r.metric == "errors.error_rate" for r in rules):
        rules.append(ThresholdRule(metric="errors.error_rate", constraints={"max_value": 0.0}))
        implicit_flags.append(True)
    verdicts = []
    for rule, implicit in zip(rules, implicit_flags):
        if rule.metric not in known:
            raise GateConfigError(
                f"thresholds reference metric '{rule.metric}' which no configured scorer "
                f"or system metric produces; available: {sorted(known)}"
            )
        if rule.metric not in baseline_aggs:
            raise GateConfigError(
                f"thresholds reference metric '{rule.metric}' missing from baseline "
                f"aggregates (present only on candidate side); available baseline: "
                f"{sorted(baseline_aggs)}"
            )
        if rule.metric not in candidate_aggs:
            raise GateConfigError(
                f"thresholds reference metric '{rule.metric}' missing from candidate "
                f"aggregates (present only on baseline side); available candidate: "
                f"{sorted(candidate_aggs)}"
            )
        _reject_direction_mismatch(rule, candidate_aggs.get(rule.metric))
        verdicts.append(
            _evaluate_rule(
                rule, baseline_aggs.get(rule.metric), candidate_aggs.get(rule.metric), implicit,
                (comparison_issues or {}).get(rule.metric),
            )
        )
    return verdicts


def _reject_direction_mismatch(rule: ThresholdRule, metric: dict) -> None:
    """A drop-guard on a lower-is-better metric (or an increase-guard on a
    higher-is-better one) can never fire on a real regression — it would be a
    gate that silently passes everything. Fail loudly at config time instead."""
    if not isinstance(metric, dict):
        raise GateConfigError(
            f"aggregate for metric '{rule.metric}' is malformed: expected a metric "
            f"dict, got {type(metric).__name__}"
        )
    direction = metric.get("direction")
    for name in rule.constraints:
        if name in _DROP_CONSTRAINTS and direction == "lower_better":
            raise GateConfigError(
                f"rule on '{rule.metric}': {name} guards higher-is-better metrics, but "
                f"this metric is lower-is-better (a drop is an improvement) — "
                f"use max_increase_abs/max_increase_pct instead"
            )
        if name in _INCREASE_CONSTRAINTS and direction == "higher_better":
            raise GateConfigError(
                f"rule on '{rule.metric}': {name} guards lower-is-better metrics, but "
                f"this metric is higher-is-better (an increase is an improvement) — "
                f"use max_drop_abs/max_drop_pct instead"
            )


def _delta(baseline_m: dict, candidate_m: dict) -> dict | None:
    if not isinstance(baseline_m, dict) or not isinstance(candidate_m, dict):
        raise GateConfigError("metric aggregates for delta must be metric dicts")
    if "available" not in baseline_m or "available" not in candidate_m:
        raise GateConfigError("metric aggregates for delta are malformed: missing 'available' key")
    if not (baseline_m.get("available") and candidate_m.get("available")):
        return None
    if "value" not in baseline_m or "value" not in candidate_m:
        raise GateConfigError("metric aggregates for delta are malformed: missing 'value' key")
    baseline_value = baseline_m.get("value")
    candidate_value = candidate_m.get("value")
    if baseline_value is None or candidate_value is None:
        raise GateConfigError("metric aggregates for delta are malformed: available value is None")
    abs_delta = candidate_value - baseline_value
    pct = None
    if baseline_value != 0:
        pct = abs_delta / abs(baseline_value) * 100
    return {"abs": abs_delta, "pct": pct}


def _comparison_issue(
    key: str, baseline: list[ItemRecord], candidate: list[ItemRecord],
) -> str | None:
    cohorts = []
    incomplete_latency = False
    for records in (baseline, candidate):
        ids = set()
        for record in records:
            if key == "errors.error_rate":
                ids.add(record.item_id)
            elif record.status == "ok":
                if key.startswith("latency."):
                    measured = record.latency_ms is not None
                    incomplete_latency |= not measured
                elif key == "tokens.total":
                    measured = record.prompt_tokens is not None and record.completion_tokens is not None
                elif key == "cost.total_usd":
                    measured = record.cost_usd is not None
                else:
                    score = record.scores.get(key)
                    if not isinstance(score, dict) or type(score.get("applicable")) is not bool:
                        raise GateConfigError(
                            f"item '{record.item_id}': comparison of '{key}' requires a boolean applicable score"
                        )
                    measured = score["applicable"]
                if measured:
                    ids.add(record.item_id)
        cohorts.append(ids)
    if cohorts[0] == cohorts[1] and not incomplete_latency:
        return None
    all_ids = {r.item_id for records in (baseline, candidate) for r in records}
    coverage = "; ".join(
        f"{side} n={len(ids)}/{len(records)}, missing item IDs={sorted(all_ids - ids)}"
        for side, records, ids in zip(("baseline", "candidate"), (baseline, candidate), cohorts)
    )
    return f"incomparable item cohorts or incomplete latency coverage: {coverage}"


def build_report(
    dataset: Dataset,
    baseline_run: RunResult,
    candidate_run: RunResult,
    scorer_config: ScorerConfig,
    scorer_infos: list[dict],
    thresholds: Thresholds,
    pricing: PricingTable,
) -> dict:
    """Assemble the full comparison report. Deliberately timestamp- and path-free
    so its content hash is stable for identical inputs (reproducibility contract);
    paths and wall-clock live in the manifest."""
    metric_keys = sorted(set(baseline_run.aggregates) | set(candidate_run.aggregates))
    comparison_issues = {}
    for key in metric_keys:
        issue = _comparison_issue(key, baseline_run.records, candidate_run.records)
        if issue:
            comparison_issues[key] = issue
    rule_verdicts = evaluate_thresholds(
        thresholds, baseline_run.aggregates, candidate_run.aggregates, comparison_issues
    )
    n_failed = sum(1 for r in rule_verdicts if r["verdict"] == "fail")
    n_warned = sum(1 for r in rule_verdicts if r["verdict"] == "warn")
    notices = []
    bound_roles = [role for role, run in (("baseline", baseline_run), ("candidate", candidate_run))
                   if run.provider_info.get("name") == "fake"
                   and run.provider_info.get("request_binding") == BINDING_SCHEME]
    if bound_roles:
        notices.append("Request-bound replay checks fixture request identities for "
                       + ", ".join(bound_roles)
                       + "; hashes do not attest model execution or producer authenticity")
    baseline_error_label = "item-processing errors" if baseline_run.n_processing_errors else "provider errors"
    candidate_error_label = "item-processing errors" if candidate_run.n_processing_errors else "provider errors"
    if baseline_run.n_errors:
        notices.append(
            f"baseline run had {baseline_run.n_errors}/{baseline_run.n_items} {baseline_error_label}; "
            f"baseline aggregates cover only the answered items"
        )
    if candidate_run.n_errors:
        notices.append(
            f"candidate run had {candidate_run.n_errors}/{candidate_run.n_items} {candidate_error_label}"
        )

    metrics = {}
    for key in metric_keys:
        b = baseline_run.aggregates.get(key)
        c = candidate_run.aggregates.get(key)
        if b is None or c is None:  # only possible with asymmetric custom scoring
            continue
        metrics[key] = {
            "baseline": b, "candidate": c,
            "delta": None if key in comparison_issues else _delta(b, c),
        }

    by_id_baseline = {r.item_id: r for r in baseline_run.records}
    by_id_candidate = {r.item_id: r for r in candidate_run.records}
    items = []
    for item in dataset.items:
        b_rec = by_id_baseline.get(item.id)
        c_rec = by_id_candidate.get(item.id)
        items.append({
            "id": item.id,
            "baseline": b_rec.to_dict() if b_rec else None,
            "candidate": c_rec.to_dict() if c_rec else None,
        })

    report = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "tool": {"name": TOOL_NAME, "version": __version__},
        "gate": {
            "verdict": "fail" if n_failed else "pass",
            "n_rules": len(rule_verdicts),
            "n_failed": n_failed,
            "n_warned": n_warned,
            "notices": notices,
        },
        "rules": rule_verdicts,
        "metrics": metrics,
        "runs": {
            "baseline": baseline_run.summary(),
            "candidate": candidate_run.summary(),
        },
        "items": items,
        "inputs": {
            "dataset": {
                "name": dataset.name, "version": dataset.version,
                "task": dataset.task, "n_items": len(dataset.items),
                "sha256": dataset.sha256,
            },
            "baseline_config": {
                "name": baseline_run.config.name, "provider": baseline_run.config.provider,
                "model": baseline_run.config.model, "sha256": baseline_run.config.sha256,
            },
            "candidate_config": {
                "name": candidate_run.config.name, "provider": candidate_run.config.provider,
                "model": candidate_run.config.model, "sha256": candidate_run.config.sha256,
            },
            "scorer_config": {"sha256": scorer_config.sha256, "scorers": scorer_infos},
            "thresholds": {"sha256": thresholds.sha256, "n_rules": len(thresholds.rules)},
            "pricing_table": {
                "version": pricing.version, "currency": pricing.currency,
                "sha256": pricing.sha256,
            },
        },
    }
    report["result_hash"] = content_hash(report)
    return report
