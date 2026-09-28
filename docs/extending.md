# Extending llm-release-gate

Three seams: **providers** (how requests get answered), **task adapters** (what an app's
inputs/outputs look like), **scorers** (what "good" means). Everything else — runner,
gate, reports — is generic and should not need changes.

Extensions currently live in-tree (fork or PR). Entry-point plugin loading is a NEXT.md
condition — it gets built when the second out-of-tree extension actually exists.

## Adding a provider

```python
# src/llm_release_gate/providers/acme.py
import os

from ..errors import ProviderError
from . import Provider, ProviderRequest, ProviderResult, register_provider

class AcmeProvider(Provider):
    name = "acme"

    def __init__(self, options: dict, base_dir: str):
        self.api_key = os.environ["ACME_API_KEY"]   # keys from env, never config files

    def complete(self, request: ProviderRequest) -> ProviderResult:
        try:
            resp = ...  # call the API with request.model / request.system / request.prompt
        except AcmeError as exc:
            raise ProviderError(f"acme: {exc}") from exc
        return ProviderResult(
            text=resp.text,
            model=request.model,
            prompt_tokens=resp.usage.input if resp.usage else None,
            completion_tokens=resp.usage.output if resp.usage else None,
            latency_ms=resp.elapsed_ms,
        )

register_provider("acme", AcmeProvider)
```

Then import it from `providers/__init__.py` alongside the fake provider.

**The honesty contract (non-negotiable for any provider):**

- Report token counts and latency only if the API actually returned/measured them —
  otherwise pass `None`. Downstream shows *unavailable*; it must never guess.
- On failure, raise `ProviderError` with a useful message. Never return placeholder text:
  a fabricated answer would be scored as if the model produced it.
- Make `describe()` return whatever pins the run's identity (endpoint, api version) —
  it lands in the manifest.
- Determinism: prefer temperature 0 / seeds where the API offers them, and say in
  `describe()` when results are inherently non-reproducible.

## Adding a task adapter

Subclass `TaskAdapter`; provide `prompt_fields(item)` (the `$fields` your users'
templates can reference) and `parse(text, item) -> ParsedOutput`. Set `name` and bump
`version` whenever parsing conventions change — the version is recorded in run manifests,
so a convention change is visible as a different run identity. Register in
`adapters/__init__.py`. Keep output conventions (citation markers, abstention phrasing)
in the adapter — scorers must stay convention-agnostic. Set `required_input`
to the input keys your prompt needs as non-empty strings (missing one is exit 2).

## Adding a scorer

```python
from ..metrics import HIGHER
from . import Scorer, item_result, register_scorer

class PolitenessScorer(Scorer):
    name = "politeness"
    version = "1"
    metrics = {
        "politeness.pass_rate": {"direction": HIGHER, "kind": "heuristic_rate", "mode": "pass_rate"},
    }

    def score_item(self, item, output):
        applicable = bool(output.text) and not output.abstained
        if not applicable:
            return {"politeness.pass_rate": item_result(applicable=False)}
        rude = "obviously" in output.text.lower()
        return {"politeness.pass_rate": item_result(
            applicable=True, passed=not rude,
            detail="contains condescension marker" if rude else None,
        )}

register_scorer("politeness", PolitenessScorer)
```

Rules:

- **One owner per metric.** `build_scorers` rejects two scorers emitting the same key.
- **Declare `kind: "heuristic_rate"`** for rule-based proxies so reports label them
  honestly. Use `mode: "violation_rate"` for lower-is-better rates (see `abstention.py`).
- **`applicable=False` over fake passes.** An item your scorer can't judge must not
  inflate the denominator.
- Options arrive via scorer config (`{"type": "politeness", "options": {...}}`); validate
  them in `__init__` and raise `GateConfigError` on nonsense — exit 2 beats a wrong verdict.
- Thresholds referencing your metric work immediately; nothing in `gate.py` changes.

## Pricing tables

Maintain your own `pricing.json` (per-MTok input/output prices), bump `version` on every
price change, and commit it next to your eval configs. Models missing from the table make
cost *unavailable* (fail-closed if you gate on cost) — that is intentional; add the model
rather than letting a stale table produce wrong dollar numbers.

## Fixture recording

There is no record mode yet (NEXT.md). To build fixtures for the fake provider today:
run your live system over the dataset once, and save each response under
`responses[<model>][<item_id>]` with real token counts and latencies — or write fixtures
by hand, as the examples do. `llm-release-gate run` (single-config) is the debugging loop
for fixture authoring.
