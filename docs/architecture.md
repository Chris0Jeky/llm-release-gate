# Architecture

One pipeline, five pinned inputs, one auditable verdict.

```
 dataset.json     baseline.json    candidate.json   scorers.json  thresholds.json  pricing.json
     │                 │                 │               │              │              │
     └── sha256 ───────┴──── sha256 ─────┴─── sha256 ────┴── sha256 ────┴── sha256 ────┘
                                        │
                              ┌─────────▼──────────┐
                              │  runner.run_config │   × 2 (baseline, candidate)
                              │  adapter → provider│
                              │  → parse → score   │
                              └─────────┬──────────┘
                                        │  per-item records + aggregates
                              ┌─────────▼──────────┐
                              │  gate.build_report │  threshold verdicts, deltas
                              └─────────┬──────────┘
                       ┌────────────────┼──────────────────┐
                 report.json       report.md          report.html     + manifest.json
                 (result_hash)     (PR comment)       (artifact)        (audit record)
```

## Module map

| Module | Owns |
|---|---|
| `loading.py` | parsing + validation of the five inputs; every loader returns a line-ending-normalized JSON source sha256 |
| `providers/` | `Provider` interface + registry; `fake.py` is the deterministic replay provider |
| `adapters/` | `TaskAdapter` interface + registry; item → prompt fields, raw text → `ParsedOutput` |
| `scorers/` | `Scorer` interface + registry + uniform aggregation; each metric has exactly one owner |
| `pricing.py` | tokens × pricing table → cost, or `(None, reason)` — never a guess |
| `runner.py` | executes one config over the dataset; per-item records; honest aggregates |
| `gate.py` | threshold engine and report assembly — the logic CI trusts |
| `manifest.py` | the audit record: paths, hashes, versions, timestamp, result hash |
| `reports/` | Markdown (PR comment), HTML (artifact); JSON is the report dict itself |
| `cli.py` | argument parsing, file writing, exit codes, GitHub env integration |

## Interfaces (the three extension seams)

- **Provider** — `complete(ProviderRequest) -> ProviderResult`. Reports only what it
  knows: `prompt_tokens` / `completion_tokens` / `latency_ms` are Optional; `None` flows
  through as *unavailable*, never as zero. Failure = raise `ProviderError` (recorded on
  the item; the run continues).
- **TaskAdapter** — `prompt_fields(item)` feeds the config's `$field` template;
  `parse(text, item)` produces `ParsedOutput` (citations, abstention, JSON body). Built-in:
  `rag`, `assistant`, `extraction`.
- **Scorer** — declares the metrics it owns (`direction`, `kind`, aggregation `mode`),
  scores one item at a time, returns per-metric `{applicable, passed, detail}`. Built-in:
  `keyword_quality`, `field_match`, `abstention`, `citations`, `json_schema`.

Registries are plain dicts populated at import; see `docs/extending.md`.

## Input schemas (by example)

**Dataset** — `{"name", "version", "task", "items": [{"id", "input", "expected"}]}`.
`task` selects the adapter. Grounded tasks: `input.question` + `input.documents[{id,text}]`,
`expected.quality.must_contain/must_not_contain`, `expected.must_cite`,
`expected.should_abstain`. Extraction: `input.text`, `expected.fields`. The `expected` sub-fields above are type-checked at load and a wrong shape is a configuration error (exit 2).
`input.question` (grounded tasks) and `input.text` (extraction) are required
non-empty strings; an item missing its task's prompt input is a configuration
error (exit 2), never an empty-prompt run. `input.documents` stays optional.

**Run config** — `{"name", "provider", "model", "params", "prompt": {"system",
"template"}, "provider_options"}`. Templates use `string.Template` syntax (`$question`,
`$documents`, `$sources`, `$text`) so JSON braces never collide. `prompt.system`, when
present, must be a string; omitting it or using an empty string is valid.

**Fake provider fixtures** — `{"responses": {"<model>": {"<item_id>": {"text",
"prompt_tokens?", "completion_tokens?", "latency_ms?", "error?"}}}}`. Omit token fields to
simulate a provider that reports no usage; an `error` entry raises `ProviderError`. `latency_ms`, when present, must be a finite non-negative number (NaN and ±Infinity are rejected as config errors).

**Scorer config** — `{"scorers": [{"type", "options?"}]}`. Two scorers may not emit the
same metric (validated at build time).

**Thresholds** — `{"rules": [{"metric", <constraints>, "level?": "fail|warn",
"on_unavailable?": "fail|warn|skip"}]}`. Constraints: `max_drop_abs`, `max_drop_pct`,
`max_increase_abs`, `max_increase_pct` (candidate vs baseline), `min_value`, `max_value`
(candidate alone).

**Pricing table** — `{"version", "currency", "models": {name: {input_per_mtok,
output_per_mtok}}}`. Version + hash land in the manifest; bump the version when prices
change.

## Verdict semantics

- Rule breach at level `fail` → gate **fail** (exit 1). `warn` only annotates.
- A rule whose metric is unavailable applies its `on_unavailable` policy — default
  **fail** (fail-closed: a gate you cannot evaluate is not a passing gate).
- A rule naming a metric nothing produces → configuration error (exit 2).
- If no rule covers `errors.error_rate`, an implicit `{max_value: 0}` fail rule is added
  for the candidate, so provider failures can't hide behind the items that succeeded.
- Score aggregates are computed over *applicable, answered* items only; every rate
  carries numerator/denominator; baseline provider errors are called out as a notice.

## Reproducibility contract

- `report.json` contains no timestamps and no filesystem paths; `result_hash` is the
  sha256 of its canonical JSON (sorted keys, compact separators, NaN rejected).
- Identical inputs ⇒ byte-identical reports and equal result hashes (enforced by
  `tests/test_reproducibility.py`).
- Input and fake-fixture hashes normalize only physical JSON line endings (CRLF or lone
  CR to LF). Escaped `\\r` and `\\n` inside JSON values remain distinct; formatting and
  substantive source changes remain pinned.
- `manifest.json` holds the volatile context: input paths and hashes, fixture hashes,
  pricing-table version, tool version, wall-clock `created_at`, and the `result_hash` it
  vouches for.

## Design decisions & non-goals

- **Zero runtime dependencies.** The gate must run anywhere CI runs; `pip install .` is
  the whole setup. Dev dependency: pytest.
- **Replay-style fake provider keyed by (model, item_id).** Authorable, deterministic and
  offline. The trade-off is explicit: fixtures don't react to prompt text — prompt-change
  effects must be captured by re-recording fixtures. Real-provider adapters are a NEXT.md
  condition, not built speculatively.
- **Heuristic scorers, honestly labeled.** Keyword/pattern checks are proxy signals; the
  report marks them as heuristics. LLM-judge scoring is deliberately out of scope for now
  (NEXT.md).
- **No baseline auto-management.** You state what baseline and thresholds are; the tool
  never silently rewrites them.
