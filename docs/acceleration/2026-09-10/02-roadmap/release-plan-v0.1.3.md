# v0.1.3 trust-alignment release plan

## Purpose

Align the current source tree, package version, licence notices, Action reference and verified artefacts after the post-v0.1.2 changes. This is a trust release, not a feature release.

## Owner gate before tagging

- `D02` confirms whether to cut v0.1.3 now.
- `D03` determines what happens to the floating `v0` tag and how the licence transition is communicated.
- No agent may infer either decision from the existence of this plan.

## Recommended scope

- Close issue #20 and update runtime/harness facts.
- Land selected P1 verdict-integrity fixes that do not introduce the snapshot schema.
- Build and install-test source distribution and wheel, including all licence files.
- Update version sources together: `pyproject.toml`, package `__version__`, measured examples/docs and release ledger.
- Add a changelog/release note that distinguishes historical MIT v0.1.2 from current GPL source.

## Exact-head release checklist

1. Reconcile `origin/main`, open PRs/issues/checks, tags, releases and Marketplace state.
2. Verify a clean worktree at the intended release commit.
3. Run narrow proving checks for every touched seam.
4. Run the full suite and green/red demos from the release tree.
5. Build `sdist` and `wheel`; inspect archive contents for `LICENSE`, `RELICENSING.md`, `LICENSES/MIT.txt`.
6. Install the wheel into a clean environment and run `--version`, `hash`, one green gate and the deliberate-red gate.
7. Run the Action self-test at the exact commit.
8. Verify public-report disclosure and Markdown escaping tests.
9. Create immutable annotated `v0.1.3` only after all exact-head checks are green.
10. Publish release notes with the licence statement.
11. Move `v0` only when the recorded `D03` option permits it; verify the peeled commit after movement.
12. Verify the Marketplace listing resolves to the intended tag/version.
13. Update `ORCHESTRATOR.md` and `HUMAN_TODO.md` with observed state, not anticipated state.

## Suggested release-note skeleton

```markdown
## llm-release-gate v0.1.3 — trust alignment

- repairs repository agent permission rules;
- hardens malformed-input and report-safety edge cases;
- verifies wheel/sdist licence contents and clean-install behaviour;
- keeps the comparison/report schema unchanged [or state the schema bump explicitly].

### Licence

v0.1.3 is distributed under GPL-3.0-only. v0.1.2 and earlier copies released under MIT retain those previously granted rights. [State the selected `v0` strategy here.]
```

## Rollback

Immutable `v0.1.3` is never moved or deleted to hide a defect. If a defect is discovered, publish a later patch and move only a permitted floating compatibility tag after review.
