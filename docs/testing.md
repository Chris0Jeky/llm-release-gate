# Testing

## Commands

```bash
make install      # pip install -e ".[dev]"
make test         # pytest (see the pinned measurement below)
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
| `test_expected_shapes.py` | dataset `expected`-block shapes validated fail-closed at load (wrong `quality` / `must_cite` / `should_abstain` / `fields` shape → config error, exit 2); well-shaped and empty blocks accepted; bad shape exits 2 end-to-end |
| `test_nonfinite_latency.py` | non-finite latency fails closed: NaN/±Infinity rejected as fixture config errors, `scalar_metric` reports them unavailable (never an available NaN), a NaN-latency candidate exits 2, and NaN aggregates stay unavailable so thresholds cannot pass on them |
| `test_required_input.py` | items missing the task's prompt input (`input.question` for grounded tasks, `input.text` for extraction — absent, blank, or wrong-key) fail closed with exit 2 / `GateConfigError`; valid items build byte-identical prompts |

The reproducibility tests also prove that changing only physical JSON source line endings
(LF, CRLF, or lone CR) leaves the report, result hash, and fake-fixture identities unchanged.

The shared fixture (`conftest.mini_gate`) builds a tiny 3-item grounded gate on disk;
tests break exactly one thing per case.

**Not covered (known, intentional):** real provider calls (no real adapter exists yet —
see NEXT.md); the Action's PR-comment step (needs a live PR; the rest of action.yml is
self-tested in CI on both examples and the step logic was exercised locally, below).

## Verified runs (2026-10-02, Windows, Python 3.14.3, pytest 9.0.3)

Measured main commit `898b9ecafe67639b55de668b3624f6720a00755a` before the
diagnostic-fix PRs. Test counts and timings describe this snapshot; they are
not a fixed suite contract. The CI workflow declares Ubuntu Python 3.11/3.13
and the Action self-test; those hosted lanes are separate evidence.

`PYTHONPATH=src make ci PY=python` with Git-for-Windows Bash as Make's shell
completed in 2.36 seconds. Its pytest step produced:

`python -m pytest` →

```
324 passed in 1.16s
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
  result hash: sha256:1384c5ac7550c2e5d713e9d5889ba6ceb144df5b467bf7c1d7b7c5429c715c77
OK: regression correctly blocked (exit 1)
```

(cost.total_usd fell 96.4% — and the gate still failed; that asymmetry is the product.)

The 2026-10-02 run used a task-owned virtual environment, reused installed pytest,
disabled unrelated global pytest plugins (`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`),
and set a task-owned pytest `--basetemp`. `PYTHONPATH=src` pinned the worktree's
source for both tests and demos. On Windows PowerShell, the source-pinned Make
invocation was:

```powershell
$env:PYTHONPATH='src'
make ci PY=python 'SHELL=C:/Program Files/Git/bin/bash.exe'
```

Without this shell override, Windows Make may misinterpret the deliberate
red-demo recipe.

Reproducibility spot-check: red-demo reports from three separate task worktrees
(main and the two diagnostic branches) were byte-identical and shared the hash
above. The full suite also exercised repeated-run and relocated-input
reproducibility (the report does not embed absolute paths).

Historical Action logic local simulation (2026-08-02; not rerun on 2026-10-02):
bash, `GITHUB_OUTPUT`/`GITHUB_STEP_SUMMARY` pointed at temp files, same commands
as action.yml. The outputs file received `verdict=fail`,
`exit-code=1`, `result-hash=…`, report paths, `cli-exit=1`; summary file received the
Markdown report; the enforce step maps `cli-exit=1` to a failed check.

## Release package acceptance

Build and check both archive types, then install the wheel into a fresh offline
environment and verify its import, entrypoint, version, hash and green/red gates:

```bash
python -m pip install build
python -m build --outdir dist
python scripts/verify_dist.py dist --smoke
```

The v0.2.0 candidate on Windows Python 3.14.3 passed 353 tests in 1.17s on
2026-10-02. Both green demos passed and the deliberate regression exited 1.
Its report hashes are `34742875a2979772b7a3db015182e3a9e9753261273953dc286f6ab815072263`
(rag), `042ad6047df0a03fb93f528c81c550964bb2a6081d0cfa25eeca36ed7e6e31d4`
(extraction), and `432ccdf9bdb263f642d5607528f4b80cfe79bd15d0603fd543fa46ab78bd7b05`
(red). The tool version is part of each report; these hashes differ from the
historical 0.1.2 measurements above. Exact release receipts live in the ledger.
Python 3.11 cost summation produces different rag/red hashes from Python 3.13+
for these inputs; observed verdicts agree. Pin the Python version when comparing
result hashes until [#69](https://github.com/Chris0Jeky/llm-release-gate/issues/69)
is resolved; this is separate from input line-ending normalization.

The verifier compares `LICENSE`, `RELICENSING.md` and `LICENSES/MIT.txt` bytes
against the checkout in both archives, checks package metadata and zero runtime
dependencies, and runs the installed wheel with isolated Python (`-I`). CI's
`package` job runs the same acceptance and preserves the archives. The v0.2.0
candidate fixes a reproduced wheel omission: `MANIFEST.in` supplied the sdist
notices but did not put all notices in the wheel; explicit `license-files` does.

## Adding tests

Break one behavior per test. Prefer driving through `cli.main([...])` (in-process, fast,
exercises loading + wiring) with `mini_gate` overrides; drop to unit level for pure logic
(verdicts, hashing, schema validation). If you add a metric or scorer, test its
*ownership* (no metric collisions), its applicability rules, and how it renders when
unavailable.
