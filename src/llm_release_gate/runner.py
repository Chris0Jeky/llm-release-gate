"""Run one configuration over the dataset and aggregate what actually happened.

Provider failures are recorded per item and the run continues; failed items are
excluded from score/latency aggregates. A post-response processing failure retains
its returned measurements but makes token/cost totals unavailable, rather than
presenting surviving-item sums as complete. Every aggregate carries its sample
count; errors.error_rate remains governed by the existing threshold policy.
"""

from __future__ import annotations

import math
import os
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Optional

from .adapters import build_adapter
from .errors import GateConfigError, ProviderError
from .loading import Dataset, PricingTable, RunConfig
from .metrics import LOWER, percentile, rate_metric, scalar_metric, unavailable_metric
from .pricing import item_cost_usd, normalize_token_count
from .providers import build_provider
from .scorers import Scorer, aggregate_scores


@dataclass
class ItemRecord:
    item_id: str
    status: str                      # "ok" | "error"
    error: Optional[str] = None
    text: Optional[str] = None
    abstained: Optional[bool] = None
    citations: list[str] = field(default_factory=list)
    parse_error: Optional[str] = None
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    latency_ms: Optional[float] = None
    cost_usd: Optional[float] = None
    cost_note: Optional[str] = None
    scores: dict = field(default_factory=dict)  # metric_key -> item_result

    error_stage: Optional[str] = None  # non-provider failure: request/response/pricing/parse/score

    def __post_init__(self) -> None:
        self.prompt_tokens = normalize_token_count(self.prompt_tokens)
        self.completion_tokens = normalize_token_count(self.completion_tokens)

    def to_dict(self) -> dict:
        payload = {
            "item_id": self.item_id,
            "status": self.status,
            "error": self.error,
            "text": self.text,
            "abstained": self.abstained,
            "citations": self.citations,
            "parse_error": self.parse_error,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "latency_ms": self.latency_ms,
            "cost_usd": self.cost_usd,
            "cost_note": self.cost_note,
            "scores": self.scores,
        }
        if self.error_stage is not None:
            payload["error_stage"] = self.error_stage
        return payload


@dataclass
class RunResult:
    config: RunConfig
    provider_info: dict
    adapter_info: dict
    records: list[ItemRecord]
    aggregates: dict  # metric_key -> MetricValue

    @property
    def n_items(self) -> int:
        return len(self.records)

    @property
    def n_ok(self) -> int:
        return sum(1 for r in self.records if r.status == "ok")

    @property
    def n_errors(self) -> int:
        return sum(1 for r in self.records if r.status == "error")

    @property
    def n_processing_errors(self) -> int:
        return sum(r.status == "error" and r.error_stage is not None for r in self.records)

    def summary(self) -> dict:
        summary = {
            "config_name": self.config.name,
            "provider": self.provider_info,
            "model": self.config.model,
            "adapter": self.adapter_info,
            "n_items": self.n_items,
            "n_ok": self.n_ok,
            "n_errors": self.n_errors,
            "aggregates": self.aggregates,
        }
        if self.n_processing_errors:
            summary["n_processing_errors"] = self.n_processing_errors
        return summary


def run_config(
    dataset: Dataset,
    config: RunConfig,
    scorers: list[Scorer],
    pricing: PricingTable,
) -> RunResult:
    adapter = build_adapter(dataset.task)
    base_dir = os.path.dirname(os.path.abspath(config.path)) if config.path else "."
    provider = build_provider(config.provider, config.provider_options, base_dir)

    records: list[ItemRecord] = []
    for item in dataset.items:
        # A fresh record per item avoids reusing a previous response on failure.
        record = ItemRecord(item_id=item.id, status="error")
        stage = "request"
        try:
            request = adapter.build_request(item, config)
            stage = "provider"
            result = provider.complete(request)
            stage = "response"
            record.text = result.text
            record.prompt_tokens = normalize_token_count(result.prompt_tokens)
            record.completion_tokens = normalize_token_count(result.completion_tokens)
            record.latency_ms = result.latency_ms
            # Capture consumption before parsing/scoring can fail. No raw provider
            # payload is copied; missing/invalid token counts remain unknown.
            stage = "pricing"
            record.cost_note = "pricing did not complete"
            record.cost_usd, record.cost_note = item_cost_usd(result, pricing)
            stage = "parse"
            parsed = adapter.parse(result.text, item)
            record.abstained = parsed.abstained
            record.citations = parsed.citations
            record.parse_error = parsed.parse_error
            stage = "score"
            scores: dict = {}
            for scorer in scorers:
                scores.update(scorer.score_item(item, parsed))
            record.scores = scores
            record.status = "ok"
        except GateConfigError:
            raise
        except Exception as exc:
            record.error = str(exc) if isinstance(exc, ProviderError) else f"{type(exc).__name__}: {exc}"
            if stage != "provider":
                record.error_stage = stage
        records.append(record)

    aggregates = _aggregate(records, scorers)
    return RunResult(
        config=config,
        provider_info=provider.describe(),
        adapter_info=adapter.describe(),
        records=records,
        aggregates=aggregates,
    )


def _stable_sum(values: Iterable[float]) -> float:
    """Use an explicit float algorithm, independent of Python's built-in sum.

    Non-representable totals remain non-finite so scalar_metric reports them
    unavailable rather than raising or substituting a partial/rounded total.
    """
    try:
        return math.fsum(values)
    except (OverflowError, ValueError):
        return math.nan


def _aggregate(records: list[ItemRecord], scorers: list[Scorer]) -> dict:
    ok = [r for r in records if r.status == "ok"]
    aggregates = aggregate_scores(scorers, [r.scores for r in ok])

    aggregates["errors.error_rate"] = rate_metric(
        len(records) - len(ok), len(records), direction=LOWER,
    )

    # Latency: computed over answered items that reported it; partial coverage is noted.
    latencies = sorted(r.latency_ms for r in ok if r.latency_ms is not None)
    if latencies:
        note = None
        if len(latencies) < len(ok):
            note = f"latency reported for {len(latencies)} of {len(ok)} answered items"
        aggregates["latency.p50_ms"] = scalar_metric(
            percentile(latencies, 50), "ms", LOWER, n=len(latencies), kind="recorded", note=note
        )
        aggregates["latency.p95_ms"] = scalar_metric(
            percentile(latencies, 95), "ms", LOWER, n=len(latencies), kind="recorded", note=note
        )
        aggregates["latency.mean_ms"] = scalar_metric(
            _stable_sum(latencies) / len(latencies), "ms", LOWER, n=len(latencies), kind="recorded", note=note
        )
    else:
        for key in ("latency.p50_ms", "latency.p95_ms", "latency.mean_ms"):
            aggregates[key] = unavailable_metric("ms", LOWER, "provider reported no latency")

    # Tokens and cost: totals only when EVERY answered item has data — a partial
    # total presented as a total would fabricate a lower number.
    with_tokens = [
        r for r in ok if r.prompt_tokens is not None and r.completion_tokens is not None
    ]
    if ok and len(with_tokens) == len(ok):
        total_tokens = sum(r.prompt_tokens + r.completion_tokens for r in ok)
        aggregates["tokens.total"] = scalar_metric(
            total_tokens, "tokens", LOWER, n=len(ok),
            note=f"prompt+completion over {len(ok)} answered items",
        )
    else:
        missing = len(ok) - len(with_tokens)
        aggregates["tokens.total"] = unavailable_metric(
            "tokens", LOWER,
            f"token usage missing for {missing} of {len(ok)} answered items"
            if ok else "no answered items",
        )

    with_cost = [r for r in ok if r.cost_usd is not None]
    if ok and len(with_cost) == len(ok):
        aggregates["cost.total_usd"] = scalar_metric(
            _stable_sum(r.cost_usd for r in ok), "usd", LOWER, n=len(ok), kind="derived",
            note=f"tokens x pricing table, over {len(ok)} answered items",
        )
    else:
        if not ok:
            reason = "no answered items"
        else:
            reasons = sorted({r.cost_note for r in ok if r.cost_note})
            reason = (
                f"no cost for {len(ok) - len(with_cost)} of {len(ok)} "
                f"answered items: {'; '.join(reasons)}"
            )
        aggregates["cost.total_usd"] = unavailable_metric("usd", LOWER, reason)

    post_response_errors = sum(
        r.status == "error" and r.error_stage in ("response", "pricing", "parse", "score")
        for r in records
    )
    if post_response_errors:
        reason = (f"totals unavailable after {post_response_errors} post-response "
                  "item-processing errors; per-item measurements retained when available")
        aggregates["tokens.total"] = unavailable_metric("tokens", LOWER, reason)
        aggregates["cost.total_usd"] = unavailable_metric("usd", LOWER, reason)

    return aggregates
