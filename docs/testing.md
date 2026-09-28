# Testing

## Commands

```bash
make install      # pip install -e ".[dev]"
make test         # pytest (84 tests)
make demo-green   # both green examples; target fails unless both exit 0
make demo-red     # red example; target fails unless the gate exits exactly 1
make ci           # test + demo-green + demo-red (what CI runs)
```

Windows note: run under Git Bash (GNU make + sh), or call the underlying
`python -m pytest` / `python -m llm_release_gate ...` commands directly.

## What the suite covers (and deliberately not)

Tests target the behaviors CI depends on — verdict logic, reproducibility, hashing, cost
math, provider failure, report honesty, exit codes — not line-coverage maximization.

| File | Guards |
|---|---|
| `test_verdicts.py` | every constraint type incl. boundaries and zero-baseline percentages; warn vs fail; `on_unavailable` fail/warn/skip; candidate-only constraints ignoring baseline availability; the implicit `errors.error_rate` rule (added, replaced, fails); unknown metric → config error; direction-mismatched constraints rejected; nearest-rank percentile math pinned |
| `test_hashing.py` | canonical-JSON invariance (key order), sensitivity (values, list order), unicode, NaN rejection, digest format, file hashing |
| `test_cost.py` | exact token×price math; missing tokens / missing model / no table → unavailable with reason; partial token data poisons totals instead of understating them; gating on unavailable cost fails closed; `on_unavailable: "skip"` flows through the CLI and renders the skipped cost rule in Markdown and HTML; boolean pricing rates rejected (never used as 1/0) |
| `test_provider_failure.py` | missing fixture and simulated `error` entries raise `ProviderError`; the run continues; failures land on items and in `errors.error_rate`; a candidate that only looks good on surviving items is blocked; baseline-side errors emit the exact notice in report JSON, Markdown, and HTML while a healthy candidate passes; all-items-failed yields unavailable score and latency metrics with no fabricated values; malformed fixture entries (negative/string tokens, non-dict) are clean config errors; error messages carry the config-relative fixtures ref, not an absolute path |
| `test_reproducibility.py` | identical inputs → byte-identical report/md/html and equal `result_hash`; report is timestamp- and path-free (incl. the fake provider's fixtures path); the same inputs run from a different directory hash identically; manifest pins hashes + verdict; changed input changes the hash |
| `test_scorers.py` | adapter parsing (citations, abstention regex, JSON fence stripping); all four abstention quadrants; hedged-fabrication answers (hedge + citation) counted as answers with citations validated; citation validity incl. fabricated citations on should-abstain items; keyword/field-match pass/fail/applicability; JSON-schema subset violations; unenforceable schemas rejected at construction; JSON-strict bool≠int semantics at every depth (incl. nested lists/dicts) |
| `test_reports.py` | rates rendered with sample counts; heuristic footnote present; unavailable cost labeled with its reason (and no fabricated `$0`); partial-coverage latency note surfaced in the markdown PR comment, not only the HTML; HTML escapes model output; failing items carry actionable detail |
| `test_cli.py` | exit 0 (both green examples), exit 1 (red example, naming the regressions), exit 2 (missing file, bad rule, metric without scorer, missing/typo'd prompt template, malformed dataset, internal error); breached warn-level rule annotates but exits 0; `GITHUB_STEP_SUMMARY` / `GITHUB_OUTPUT` writing; `hash` and `run` subcommands |
| `test_nonfinite_latency.py` | non-finite latency fails closed: NaN/±Infinity rejected as fixture config errors, `scalar_metric` reports them unavailable (never an available NaN), a NaN-latency candidate exits 2, and NaN aggregates stay unavailable so thresholds cannot pass on them |

The reproducibility tests also prove that changing only physical JSON source line endings
(LF, CRLF, or lone CR) leaves the report, result hash, and fake-fixture identities unchanged.

The shared fixture (`conftest.mini_gate`) builds a tiny 3-item grounded gate on disk;
tests break exactly one thing per case.

**Not covered (known, intentional):** real provider calls (no real adapter exists yet —
see NEXT.md); the Action's PR-comment step (needs a live PR; the rest of action.yml is
self-tested in CI on both examples and the step logic was exercised locally, below).

## Verified runs (2026-08-02, Windows 10, Python 3.14.3; CI mirrors on ubuntu 3.11/3.13)

`python -m pytest` →

```
84 passed in 0.53s
```

`make demo-green` → both gates PASS, exit 0. RAG example (prompt improvement):
quality 7/8 → 8/8, cost +11.8% (≤ 25% cap), all citations valid. Extraction example
(safe cheap swap): 6/6 fields, 6/6 schema-valid, cost −95.5%.

`make demo-red` → gate FAIL, exit 1, blocked on exactly the injected regressions:

```
llm-release-gate: gate FAIL
  rules: 7 evaluated, 3 failed, 0 warned
  [FAIL] quality.pass_rate: drop 0.375 vs allowed 0.1
  [FAIL] abstention.false_answer_rate: candidate 1 vs allowed maximum 0
  [FAIL] citations.valid_rate: drop 0.3 vs allowed 0.05
  result hash: sha256:df684a0135c1cce66ca8977cd5c8234d710324010125e27c828d2fcecbb282f8
OK: regression correctly blocked (exit 1)
```

(cost.total_usd fell 96.4% — and the gate still failed; that asymmetry is the product.)

Reproducibility spot-check: consecutive red-example runs — and runs from a different
checkout directory — produced byte-identical `report.json` and the same `result_hash`
shown above (the report no longer embeds any absolute path).

Action logic local simulation (bash, `GITHUB_OUTPUT`/`GITHUB_STEP_SUMMARY` pointed at
temp files, same commands as action.yml): outputs file received `verdict=fail`,
`exit-code=1`, `result-hash=…`, report paths, `cli-exit=1`; summary file received the
Markdown report; the enforce step maps `cli-exit=1` to a failed check.

## Adding tests

Break one behavior per test. Prefer driving through `cli.main([...])` (in-process, fast,
exercises loading + wiring) with `mini_gate` overrides; drop to unit level for pure logic
(verdicts, hashing, schema validation). If you add a metric or scorer, test its
*ownership* (no metric collisions), its applicability rules, and how it renders when
unavailable.
