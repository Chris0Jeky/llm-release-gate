# llm-release-gate orchestration ledger

This is the concise, resumable control plane for a cold agent session. It does not override
repository policy; live evidence always wins.

## Current checkpoint

- **Authority:** T2 `daily-driver` in `.agent-harness/tier.json`; push and merge are free only
  after the repository gate is met.
- **Identity:** the public repository was renamed to
  [`Chris0Jeky/llm-release-gate`](https://github.com/Chris0Jeky/llm-release-gate) on 2026-08-02.
- **Release state:** GPL [v0.2.0](https://github.com/Chris0Jeky/llm-release-gate/releases/tag/v0.2.0)
  was published 2026-10-02 at 23:14:53 UTC. Both annotated `v0.2.0` and floating
  `v0` peel to `d3e80877f0bdd309a049aba5dfdfd49ea032a1d9`. Historical MIT
  `v0.1.0` (`0e0f480`), `v0.1.1` (`5514019`) and `v0.1.2` (`5c36235`) retain
  their exact tag objects and targets. See [verified receipt](docs/releases/v0.2.0.md).
- **Marketplace:** the public listing's Latest display resolves to v0.2.0 with the
  existing **Continuous integration** and **Code quality** categories. Its release
  chooser still contains only v0.1.2; registering v0.2.0 through the existing
  release editor remains unexecuted because no Computer Use runtime was callable.
- **Decisions:** q-1 and q-3 are complete; q-2 is deliberately deferred; q-4 waits for two
  real users. q-5/q-6 are approved: publish the strict GPL release and move `v0`
  to it. This exact transition is published and verified; approval was received
  2026-10-02 at 22:45:50 UTC. The Marketplace UI task requires no new product decision.
- **Release evidence:** #68 fixed reproduced wheel notice omission #67 and aligned
  version sources at 0.2.0. Exact merged-head Windows CI passed 356 tests and demos;
  hosted Ubuntu Python 3.11/3.13 passed 360 tests each, package acceptance and Action
  self-test. Published assets match the tested uploads; the tagged source archive
  matches all 149 tracked Git blobs. #65 is resolved by the chosen strict contract.
- **Known limitation:** [#69](https://github.com/Chris0Jeky/llm-release-gate/issues/69)
  records cross-Python cost precision/report-hash drift; observed verdicts agree.
  Pin Python when comparing hashes. Live PR-comment delivery, PyPI and real-provider
  execution remain unverified and were not enabled.
- **Known low item:** issue #7's stale proving-check count was corrected and closed by PR #9;
  it never blocked the release.
- **Release proof:** the prior 227-character Action description was corrected to 122 characters;
  local full tests and `make ci` passed at `5c36235`; hosted CI/action self-test and Dependency
  Graph both succeeded at that exact SHA. Remote tags and releases were verified after
  publication.
- **Historical audit:** merged PR evidence remains in GitHub and Git history. This file keeps
  the next decision and exact resume path, not a duplicate transaction log.

## Source-of-truth precedence

1. Current Git SHA, local changes, hosted CI/checks, review threads, and GitHub PR/issue state.
2. Applicable global working agreement and `~/.claude/ESTATE.md` for checkout identity.
3. `AGENTS.md`, `CLAUDE.md`, and the strictest `.agent-harness/tier.json` authority.
4. `HUMAN_TODO.md` for owner-only decisions.
5. This checkpoint for queue selection and evidence recording.
6. `README.md`, `NEXT.md`, and `docs/` for product and verification context.

## Cold-start autonomous loop

1. Read the global estate registry and the five local files in `AGENTS.md`'s order, then refresh
   the live state above. Reconcile any handoff against the exact current head before trusting it.
2. Finish an in-flight PR, failed exact-head check, or confirmed correctness/security/data-loss
   defect first. Otherwise choose the smallest reversible task that advances the current stage
   ladder below and has a named proving check.
3. Keep one writer per checkout and one coherent slice per PR. Run the narrowest stated check,
   complete the declared review/CI gate, and re-prove the exact head after it changes.
4. If a stage reaches an owner-only gate, record the evidence and one clear q-N in
   `HUMAN_TODO.md`, mark the stage blocked, and continue with the next safe unblocked stage.
   Never work around an agreement, identity, secret, spending, or publication choice.
5. At a stage transition or blocker, update this checkpoint with changed / verified / NOT
   verified / residual risk / open human action / exact resume point. Stop only when no useful
   unblocked work remains; `NEXT.md` triggers are not permission to invent work.

## Release and maintenance ladder

| Stage | State | Agent-owned next action | Owner-only stop condition |
|---|---|---|---|
| Repository identity | COMPLETE | Keep all canonical references on `Chris0Jeky/llm-release-gate`. | None. |
| Release readiness | COMPLETE | PR #10 merged after exact-head local/hosted checks and independent review. | None. |
| Public Action releases | COMPLETE | v0.2.0/v0 peel to reviewed `d3e8087`; historical MIT tags remain unchanged. | None. |
| Next Action release | COMPLETE | Strict GPL v0.2.0 publication, package/clean-install/Action checks, remote peeling and downloaded assets verified. | None: q-5/q-6 approved this exact strategy. |
| Marketplace | UI TASK PENDING | Latest display shows v0.2.0; register it in the version chooser via the existing release editor and verify. | Tool capability; stop if a new agreement/identity prompt appears. |
| PyPI | DORMANT | Do nothing until a real `pip install` request; then re-open q-2 and use Trusted Publishing. | Publishing identity/account configuration. |
| Real provider | DORMANT | Do nothing until two real users request live-model runs; then implement only the requested provider. | Provider, secret path, and `sensitive_data` review. |
| Product maintenance | TRIGGER-DRIVEN | Work a verified failure, confirmed defect, or observable `NEXT.md` trigger. | Any new privacy, retention, hosting, or spending decision. |

`v0` is a compatibility alias, not an unattended automation target: move it only as part of a
reviewed, verified 0.x release after its immutable version tag is cut. A breaking CLI/schema/
metric change is a major version event and must not move `v0`.

For v0.2.0 only, the owner explicitly selected strict identifiers despite the
historical numeric coercion and approved publishing GPL and moving `v0` to it.
This specific pre-1.0 transition is an exception to the default rule above;
it does not authorize future unattended breaking tag moves. Earlier immutable
MIT tags/releases and attribution must remain unchanged.

## Runtime boundary

The local tier currently declares the Claude runtime only. This documentation makes a cold agent
session discoverable; it does **not** install or claim a Codex deny-floor adapter. Adding another
runtime or a repo safety adapter is a separate harness-reviewed change and is intentionally out
of this release slice.

## Verification baseline

- In a linked worktree, use `PYTHONPATH=src py -3 -m pytest`; the editable install can otherwise
  resolve the primary checkout.
- `PYTHONPATH=src py -3 -m pytest` exercises the full suite. `make ci` runs tests plus the green
  and deliberately red demos. Under this Windows machine, invoke `make` through Git-for-Windows
  Bash with `PYTHONPATH=src`.
- `action.yml` is proven by the hosted `action-self-test` CI lane. Release tags require green CI
  at their exact commit and remote tag/release verification.

## External reconciliation

The global estate registry still has a stale entry for the old repository name and earlier
runtime/human-todo posture. It must be corrected in its owning `claude-config` repository, not
from this repository or this session. This repo's local tier declaration is the authority here.

## Resume

**Exact resume point:** GPL v0.2.0 and the `v0` transition are published and
verified. Reconcile live state, then finish the Marketplace version-chooser UI
task through the existing release editor when a UI runtime is available. Do not
duplicate the release or move either tag. Next bounded maintenance scope is #69's
observed cross-Python cost/hash drift; preserve fail-closed and unknown-cost semantics.
Otherwise work only a verified failure, confirmed defect, or an
observable `NEXT.md` trigger; if none
exists, stop with this checkpoint rather than inventing PyPI, provider, scheduler, hook, or
hosted-platform work.
