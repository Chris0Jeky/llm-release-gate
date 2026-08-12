# llm-release-gate

**Stop unsafe prompt, model, retrieval, tool, or configuration changes from being merged.**

llm-release-gate is an open-source CLI and GitHub Action that runs your **baseline** and
**candidate** LLM app configurations against a versioned **golden / replay dataset**,
compares them on **quality, abstention behavior, citation validity, schema validity,
latency, token use and cost**, posts a concise summary on the pull request, and **fails
the check when a configured regression threshold is breached**.

It runs entirely offline out of the box: the deterministic fake provider replays
committed fixtures, so the demo, the tests and CI need **no API key**.

## Why

A one-line change to a prompt, a model swap, a new retrieval setting, or a tool-config
tweak can quietly wreck answer quality while looking harmless in a diff. llm-release-gate
makes those changes *measurable* and *blockable* at review time — not discovered in
production.

## Quickstart (no API key needed)

```bash
make install     # pip install -e ".[dev]"
make test        # 84 tests, < 1 s
make demo-green  # two safe changes -> gate PASS (exit 0)
make demo-red    # a deliberate regression -> gate FAIL (exit 1)
```

The red demo is the whole product in one run: the candidate swaps `demo-pro-1` for
`demo-mini-1` and cuts cost **96%** — and the gate still blocks it:

```
llm-release-gate: gate FAIL
  rules: 7 evaluated, 3 failed, 0 warned
  [FAIL] quality.pass_rate: drop 0.375 vs allowed 0.1
  [FAIL] abstention.false_answer_rate: candidate 1 vs allowed maximum 0
  [FAIL] citations.valid_rate: drop 0.3 vs allowed 0.05
```

Cheaper is not the same as safe. The extraction example shows the mirror image: a model
swap that *also* saves ~95% but holds quality — and passes.

## How it works

You commit five small JSON files (all content-hashed into a run manifest):

| Input | What it is |
|---|---|
| dataset | versioned golden items: input + expectations per item |
| baseline config | the configuration that is live today (provider, model, prompt) |
| candidate config | the change under review |
| scorer config | which scorers judge the outputs |
| thresholds | what counts as a material regression |

```bash
llm-release-gate gate \
  --dataset dataset.json --baseline baseline.json --candidate candidate.json \
  --scorers scorers.json --thresholds thresholds.json \
  --pricing pricing.json --out out/
```

The gate runs both configs over the dataset, scores every item, aggregates, evaluates the
threshold rules, and writes `report.json`, `report.md`, `report.html` and `manifest.json`.

**Exit codes:** `0` pass · `1` regression blocked · `2` gate could not run
(misconfiguration is never a silent pass).

### Metrics

| Metric | Source | Direction |
|---|---|---|
| `quality.pass_rate` | `keyword_quality` (heuristic) or `field_match` (exact) | higher better |
| `abstention.false_answer_rate` | answered when it should have abstained | lower better |
| `abstention.over_abstention_rate` | abstained on answerable items | lower better |
| `citations.valid_rate` | citations exist, point at real provided sources, cover must-cites | higher better |
| `schema.valid_rate` | output parses and matches the JSON schema | higher better |
| `latency.p50_ms` / `p95_ms` / `mean_ms` | provider-reported latency | lower better |
| `tokens.total` / `cost.total_usd` | provider-reported usage × versioned pricing table | lower better |
| `errors.error_rate` | provider failures | lower better |

Threshold rules combine `max_drop_abs` / `max_drop_pct` / `max_increase_abs` /
`max_increase_pct` (candidate vs baseline) and `min_value` / `max_value` (candidate
alone), each at level `fail` or `warn`. See `examples/*/thresholds.json`.

### Honest numbers, by construction

- Every rate is reported **with its sample counts** ("7/10 (70.0%)"), computed over
  applicable items only.
- Heuristic scores are labeled as heuristics — never presented as probabilities.
- Cost and token data are **never fabricated**: if the provider doesn't report usage or
  the model isn't in your pricing table, the metric is *unavailable* with the reason, and
  rules on unavailable metrics **fail closed** by default (`on_unavailable` is
  configurable).
- Provider failures can't hide: if your thresholds don't gate on `errors.error_rate`, an
  implicit `max_value: 0` rule is added for the candidate.
- The report is timestamp-free and path-free; its `result_hash` plus the manifest's input
  hashes make every verdict reproducible and auditable.

## GitHub Action

The public `v0` reference is created with the initial `v0.1.0` release. Until that release is
visible, no remote Action reference is available: clone this repository to run its CLI/examples,
or use `uses: ./` only from a workflow inside a checkout of this repository.

```yaml
permissions:
  contents: read
  pull-requests: write   # needed for the PR comment; without it the comment
                         # becomes a warning and the verdict still stands
steps:
  - uses: actions/checkout@v5
  - uses: Chris0Jeky/llm-release-gate@v0 # or, inside this repo's checkout only: uses: ./
    with:
      dataset: eval/dataset.json
      baseline: eval/baseline.json
      candidate: eval/candidate.json
      scorers: eval/scorers.json
      thresholds: eval/thresholds.json
      pricing: eval/pricing.json         # optional
      comment: "true"                    # posts/updates the PR comment
```

The public Action's setup uses the Node 24 runtime. GitHub-hosted runners already meet its
runner requirement; self-hosted runners must use GitHub Actions Runner **2.327.1 or newer**.

The Action installs the CLI, runs the gate, writes the job summary, posts the Markdown
report as a PR comment (also when it fails — that's the point), and fails the check on
regression. Outputs: `verdict`, `result-hash`, `report-json|md|html`. This repo's own CI
self-tests the Action on both the green and the red example.

`@v0` is the compatibility reference for the latest verified 0.x release. Pin a full commit
SHA when an immutable supply-chain reference is required. The repository never moves `v0`
outside a reviewed 0.x release.

## Examples

- `examples/rag-support-bot/` — RAG application; prompt improvement, **passes**
- `examples/extraction-api/` — structured extraction; safe cheaper model swap, **passes**
- `examples/assistant-cheap-regression/` — source-grounded staff assistant; cheap model
  that fabricates policy and citations, **blocked**

All models and prices in the examples are fictional (`demo-pro-1`, `demo-mini-1`); the
fake provider replays committed fixtures byte-for-byte.

## Documentation

- [docs/architecture.md](docs/architecture.md) — pipeline, schemas, metric and verdict semantics, reproducibility contract
- [docs/testing.md](docs/testing.md) — test map plus verified commands and outputs
- [docs/extending.md](docs/extending.md) — adding providers, task adapters and scorers
- [CLAUDE.md](CLAUDE.md) — working agreements for coding agents: commands, per-seam proving checks, invariants, pitfalls
- [NEXT.md](NEXT.md) — what would make this grow into a release-management platform (and what won't)

## License

GPL-3.0-only - see [LICENSE](LICENSE) and [RELICENSING.md](RELICENSING.md).
