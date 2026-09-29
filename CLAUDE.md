# CLAUDE.md — llm-release-gate

**T2 daily driver** · push free / merge free · single-runtime (Claude) · tier + flags:
`.agent-harness/tier.json` · human decisions: `HUMAN_TODO.md`. Global laws are injected
from `~/.claude/rules/laws.md`; this file carries only what is true of *this* repo.

## What this is

Open-source CLI + GitHub Action that blocks unsafe LLM-app changes. Given five pinned JSON
inputs (dataset, baseline config, candidate config, scorers, thresholds — plus an optional
pricing table) it runs baseline and candidate over the golden dataset, scores both, writes
`report.{json,md,html}` + `manifest.json`, and exits **0 pass / 1 regression blocked /
2 could-not-run**. Zero runtime dependencies; offline by default — the `fake` provider
replays committed fixtures, so tests, demos and CI need no API key. Package version is v0.1.2;
the current public-release stage lives in `ORCHESTRATOR.md`.

## Run it (measured 2026-08-02, Windows, Python 3.14.3)

| Goal | Command | Result here |
|---|---|---|
| dev install | `make install` (`pip install -e ".[dev]"`) | — |
| full suite | `python -m pytest` | `84 passed in 0.53s` |
| green demos | `make demo-green` | both gates PASS, exit 0 |
| red demo | `make demo-red` | gate FAIL, exit 1 (that is success) |
| what CI runs | `make ci` | test + demo-green + demo-red |

`make` resolves under Git Bash on this box; without it, copy the exact
`python -m llm_release_gate gate --dataset … --out …` argument list out of the Makefile.

**Worktree trap (measured).** The editable install resolves to the MAIN checkout, so a bare
`python -m pytest` inside a linked worktree silently tests the *other* tree's source. In a
worktree, prefix everything: `PYTHONPATH=src python -m pytest`, `PYTHONPATH=src python -m
llm_release_gate …`.

## Cold start and progression

Read `~/.claude/ESTATE.md` before working an unfamiliar checkout, then this file, `.agent-harness/tier.json`, `ORCHESTRATOR.md`, `HUMAN_TODO.md`, and `NEXT.md`. Refresh
`git status --short --branch`, worktree occupancy, `origin/main`, open PRs/issues/checks/review
threads, and GitHub release/tag state. The ledger supplies the release/maintenance ladder and
exact resume point; live evidence outranks it.

Finish an in-flight PR, exact-head failure, or confirmed correctness/security/data-loss defect
first. Otherwise take the smallest reversible stage task with a named proving check. If an
owner-only gate blocks that stage, record one clear question and evidence in `HUMAN_TODO.md`,
update the ledger checkpoint, and continue with the next safe stage. Do not invent provider,
publishing, harness, scheduler, or platform work merely to fill the queue.

## Proving checks by seam

Run the narrowest row that covers your diff; each is well under a second.

| You changed | Run (`pytest` = `python -m pytest`) |
|---|---|
| `scorers/`, `adapters/` | `pytest tests/test_scorers.py` (20) |
| `gate.py`, threshold rules | `pytest tests/test_verdicts.py` (15) |
| `reports/`, `metrics.py` | `pytest tests/test_reports.py` (5) |
| `pricing.py` | `pytest tests/test_cost.py` (8) |
| `cli.py`, exit codes, GH env vars | `pytest tests/test_cli.py` (13) |
| `providers/`, `runner.py` | `pytest tests/test_provider_failure.py` (9) |
| anything in the report dict | `pytest tests/test_hashing.py tests/test_reproducibility.py` (14) |
| `examples/`, fixtures, thresholds | `make demo-green && make demo-red` |
| `action.yml` | not runnable locally — the CI `action-self-test` lane is the only proof |

Touching schemas, metric keys, exit codes or CLI flags: run `make ci` before pushing.

## Map

`loading` (parse + sha256 the five inputs) → `runner` (adapter → provider → parse → score,
once per config) → `gate` (threshold engine, report assembly) → `reports/` + `manifest`.
Three extension seams, all plain-dict registries populated at import: `providers/` (`fake`
only — deterministic replay keyed by model + item_id), `adapters/` (`rag`, `assistant`,
`extraction`), `scorers/` (`keyword_quality`, `field_match`, `abstention`, `citations`,
`json_schema`). Pipeline + schemas: `docs/architecture.md` · extending:
`docs/extending.md` · test map: `docs/testing.md`.

## Invariants (violating one is a bug, not a style choice)

1. **Never fabricate numbers.** Unknown tokens/latency stay `None`; unknown cost is
   *unavailable + reason*. No defaults, no estimates, no partial sums shown as totals.
2. **Fail closed.** Unevaluable rules fail; misconfiguration is exit 2, never a silent pass;
   provider errors surface in `errors.error_rate` (implicit rule if you do not gate on it).
3. **Reproducible report.** `report.json` holds no timestamps and no filesystem paths —
   volatile context lives in `manifest.json`. New report fields must be deterministic.
4. **Honest presentation.** Rates ship with sample counts; heuristic scores are labeled
   `kind: "heuristic_rate"`, never called probabilities or accuracy.
5. **Exit codes are API** — so are Makefile target names, CLI flags, input schemas and
   metric keys. Breaking one is a major-version event.
6. **One owner per metric.** Scorers declare direction/kind/mode and skip inapplicable items
   rather than passing them.
7. **Zero runtime dependencies.** A new runtime dep needs a NEXT.md-level justification.

New behavior lands with the test that pins it; schema/metric/command changes update the docs
in the same commit, and README output blocks must match what the code actually prints.

## Pitfalls

- `examples/assistant-cheap-regression` is *deliberately* red — never "fix" it; CI asserts
  it fails the gate. The two green examples must likewise keep exiting 0.
- `action.yml` passes inputs through `env:`, never `${{ }}` inside a `run:` body (expression
  injection). Keep it that way, and keep the PR-comment step non-fatal: a missing
  `pull-requests: write` is a warning; the gate's verdict decides the check.
- Docs quote measured numbers (test count, demo result hashes, cost deltas). Change behavior
  → re-run and re-quote. A stale hash in `docs/testing.md` is a false measurement, not a typo.
- `out/` is gitignored build output, not source.
- No deny floor is vendored here, and none runs for Claude on DESKTOP-IHKOOJS (owner decisions of
  2026-09-07/09-20; Kraspyon keeps a user-scope hook, which a repo copy would double-spawn
  against). Act as if nothing catches an irreversible command.
- **No secrets, ever.** No real provider exists yet; when one lands it reads keys from the
  environment only (`os.environ[...]`, `docs/extending.md`) — never a config file, never
  committed. That first adapter also triggers a `sensitive_data` flag review (`NEXT.md`).

## Growth

`NEXT.md` — trigger → feature table (build on the trigger, not before) and the non-goals.
`HUMAN_TODO.md` — open human decisions: Action reference name, tags, PyPI, Marketplace.
