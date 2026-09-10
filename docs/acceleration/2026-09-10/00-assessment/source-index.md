# Evidence and source index

This bundle was prepared against `main` at `f9fe5adfd4c2d7e1ea5c982fd686a173e3e910cb` on 9 September 2026.

## Repository sources inspected

### Product and operation

- `README.md`
- `pyproject.toml`
- `action.yml`
- `.github/workflows/ci.yml`
- `Makefile`
- `MANIFEST.in`
- `RELICENSING.md`
- `LICENSE`
- `LICENSES/MIT.txt`

### Source architecture

- `src/llm_release_gate/__init__.py`
- `src/llm_release_gate/cli.py`
- `src/llm_release_gate/errors.py`
- `src/llm_release_gate/gate.py`
- `src/llm_release_gate/hashing.py`
- `src/llm_release_gate/loading.py`
- `src/llm_release_gate/manifest.py`
- `src/llm_release_gate/metrics.py`
- `src/llm_release_gate/pricing.py`
- `src/llm_release_gate/runner.py`
- `src/llm_release_gate/adapters/*`
- `src/llm_release_gate/providers/*`
- `src/llm_release_gate/reports/*`
- `src/llm_release_gate/scorers/*`

### Tests and examples

- `tests/`
- `examples/rag-support-bot/`
- `examples/extraction-api/`
- `examples/assistant-cheap-regression/`

### Governance and horizon

- `AGENTS.md`
- `CLAUDE.md`
- `ORCHESTRATOR.md`
- `HUMAN_TODO.md`
- `NEXT.md`
- `.agent-harness/tier.json`
- `.claude/settings.json`
- `docs/architecture.md`
- `docs/testing.md`
- `docs/extending.md`

### GitHub history

- Issues #1, #7 and #20
- Pull requests #2–#19
- Releases v0.1.0, v0.1.1 and v0.1.2
- Annotated tags `v0`, `v0.1.0`, `v0.1.1`, `v0.1.2`
- Compare range `5c362358...f9fe5ad`
- Latest observed CI run `31659253403`

## External primary documentation consulted

These are landscape/security references, not dependencies:

- Promptfoo CI/CD: https://www.promptfoo.dev/docs/integrations/ci-cd/
- Promptfoo GitHub Action: https://www.promptfoo.dev/docs/integrations/github-action/
- Promptfoo introduction: https://www.promptfoo.dev/docs/intro/
- DeepEval CI/CD: https://deepeval.com/docs/evaluation-unit-testing-in-ci-cd
- DeepEval design philosophy: https://deepeval.com/docs/introduction-design-philosophy
- Braintrust experiments: https://www.braintrust.dev/docs/evaluate/run-evaluations
- GitHub secure `pull_request_target`: https://docs.github.com/en/actions/reference/security/securely-using-pull_request_target
- GitHub script injection guidance: https://docs.github.com/en/actions/concepts/security/script-injections
- GitHub Action reference pinning: https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/find-and-customize-actions

## Limitations

- The repository was not executed locally in this sandbox because outbound DNS prevented cloning.
- Test counts and execution state are based on the repository's measured docs and observed GitHub Actions result.
- Branch protection/rulesets could not be read through the connector (403).
- Competitor capabilities can change; use the official links above when making a later product decision.
