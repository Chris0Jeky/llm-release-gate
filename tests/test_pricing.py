"""Negative and non-integer token counts must not produce a cost."""

from llm_release_gate.loading import PricingTable
from llm_release_gate.pricing import item_cost_usd
from llm_release_gate.providers import ProviderResult
from llm_release_gate.runner import ItemRecord, _aggregate

PRICING = PricingTable(
    version="test-1",
    currency="USD",
    models={"m": {"input_per_mtok": 2.0, "output_per_mtok": 4.0}},
    path="pricing.json",
    sha256="sha256:x",
)


def test_negative_prompt_tokens_yield_no_cost():
    r = ProviderResult(
        text="", model="m", prompt_tokens=-1000000, completion_tokens=0
    )
    cost, note = item_cost_usd(r, PRICING)
    assert cost is None
    assert note


def test_negative_completion_tokens_yield_no_cost():
    r = ProviderResult(text="", model="m", prompt_tokens=10, completion_tokens=-5)
    cost, note = item_cost_usd(r, PRICING)
    assert cost is None
    assert note


def test_non_integer_token_counts_yield_no_cost():
    cases = [
        (100.0, 0),
        (100, 0.5),
        (True, 0),
        (100, False),
        ("100", 0),
    ]
    for prompt_tokens, completion_tokens in cases:
        r = ProviderResult(
            text="",
            model="m",
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )
        cost, note = item_cost_usd(r, PRICING)
        assert cost is None, (prompt_tokens, completion_tokens)
        assert note, (prompt_tokens, completion_tokens)


def test_invalid_token_counts_are_removed_before_aggregation():
    cases = [
        (-1, 0),
        (0, -1),
        (1.5, 0),
        (0, 1.5),
        (True, 0),
        (0, False),
    ]
    for prompt_tokens, completion_tokens in cases:
        record = ItemRecord(
            item_id="bad-usage",
            status="ok",
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )
        report_record = record.to_dict()
        assert report_record["prompt_tokens"] is None or (
            type(report_record["prompt_tokens"]) is int
            and report_record["prompt_tokens"] >= 0
        )
        assert report_record["completion_tokens"] is None or (
            type(report_record["completion_tokens"]) is int
            and report_record["completion_tokens"] >= 0
        )
        assert _aggregate([record], [])["tokens.total"]["available"] is False
