"""Cost computation. The one rule: never fabricate.

Cost for an item exists only when the provider reported BOTH token counts AND
the model is present in the supplied pricing table. Anything else returns
(None, reason). Totals require every answered item to have a cost — a partial
sum presented as "total cost" would understate, so it is reported unavailable
with the reason instead.
"""

from __future__ import annotations

from typing import Optional

from .loading import PricingTable
from .providers import ProviderResult


def item_cost_usd(
    result: ProviderResult, pricing: PricingTable
) -> tuple[Optional[float], Optional[str]]:
    """Return (cost, None) or (None, reason-it-is-unavailable)."""
    if result.prompt_tokens is None or result.completion_tokens is None:
        return None, "provider reported no token usage"
    for tokens in (result.prompt_tokens, result.completion_tokens):
        if type(tokens) is not int or tokens < 0:
            return None, "provider reported no token usage"
    if result.model not in pricing.models:
        if pricing.path is None:
            return None, "no pricing table supplied"
        return None, (
            f"model '{result.model}' not in pricing table "
            f"(version {pricing.version})"
        )
    rates = pricing.models[result.model]
    cost = (
        result.prompt_tokens / 1_000_000 * rates["input_per_mtok"]
        + result.completion_tokens / 1_000_000 * rates["output_per_mtok"]
    )
    return cost, None
