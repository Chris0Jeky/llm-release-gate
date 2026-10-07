# llm-release-gate orchestration ledger

This is the concise, resumable control plane for a cold agent session. It does not override
repository policy; live evidence always wins.

## Current checkpoint

- **Additive product progress:** #82 is merged as
  `827c050e987b6b90009d6efc51528c61c21a25d7`, adding opt-in byte limits and
  failure-sensitive diagnostic runs; #30 is resolved by that explicit compatible
  policy, not by silently changing defaults. Its PR-head CI run `37554304564`
  passed all jobs, including actual Action refusal, on `ec5603f006c8caa824fb34b99535da2730a05c7a`.
- **Request evidence:** #83 is merged as
  `7a343351d55427d010f288016d12fff2a72d79fc`, adding offline `plan`, opt-in rendered-request
  fingerprints and independent CLI/Action binding requirements. The synthetic
  `make demo-bound` proves accepted replay and stale-evidence refusal. Read
  [request-binding semantics and limits](docs/request-binding.md); matching content
  is not producer authenticity or model-execution proof. PR-head CI run
  `37556565750` qualified `17b5fb481f1bce3e7276678a244f1c8937f138fa` in all five jobs.
  The installed-feature smoke follow-up adds fresh-wheel checks for the new
  commands; see [progress and qualification receipts](docs/request-evidence-progress.md).
  Its own current-head CI is required, not a transfer of prior receipts.
- **Release boundary:** these additions are unreleased main. No version tag,
  provider credentials or publication settings were changed.

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
- **Maintenance:** PRs #78, #79 and #80 are merged, repairing cross-Python aggregation
  (#69), unbundler selection/dependency blockers (#22), and repository permission
  rules (#20). Their integrated source passes 407 tests and all hosted jobs.
  See [exact-head receipts and remaining work](docs/maintenance-78-80.md).
- **Numerical scope:** #69 is fixed on main, with all nine demo report artifacts
  compared across actual Python 3.11/3.13 jobs. The published v0.2.0/v0 tags were
  not moved by this maintenance pass; pin Python for historical released hashes.
  See [numerical guarantees and limits](docs/numerical-reproducibility.md).
  Live PR-comment delivery, PyPI and real-provider execution remain unverified.
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

The prior checkpoint recorded a stale global estate entry for the old repository name and
earlier runtime/human-todo posture. The maintenance pass did not inspect or modify that
owner-machine registry. Reconcile it in its owning `claude-config` repository, not by assuming
this local checkout controls it. This repo's local tier declaration is the authority here.

## Resume

**Exact resume point:** reconcile live main, open PRs, reviews and exact-head CI first.
PRs #78-#83 are merged. Reconcile the installed-feature smoke follow-up and any
later review findings against its current head before selecting more work. Do not redo completed
permission/unbundler/numerical/downloader/input-control repairs.

#30 is now resolved through the opt-in API in #82. Remaining entry-gated work is
#35 (the explicitly deferred real-provider latency boundary) and #24 (a qualified,
approved pinned consumer fixture pair before a report-only adapter). Request-bound
fake replay is not that HQ importer and does not claim its entry conditions are met.
Use their latest reconciliation comments and [the maintenance receipt](docs/maintenance-78-80.md).
Do not infer an implementation mandate from historical acceleration proposals.

GPL v0.2.0 and the prior `v0` transition remain published release receipts, not permission
for another unattended tag move. The Marketplace version-chooser task is the last recorded
UI follow-up; re-check it when an appropriate UI runtime is available. Do not duplicate the
release. Otherwise work only a verified failure, confirmed defect, or observable `NEXT.md`
trigger rather than inventing PyPI, provider, scheduler, hook, or hosted-platform work.
