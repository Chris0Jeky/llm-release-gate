# llm-release-gate orchestration ledger

This is the concise, resumable control plane for a cold agent session. It does not override
repository policy; live evidence always wins.

## Current checkpoint

- **Consumer-policy progress:** independently merged #88 was reconciled before
  this pass. #89 and #90 are merged, repairing lost post-response measurements
  and the field-match sentinel false positive. Field-match is now version 3;
  extraction hashes change deliberately. See [receipts](docs/consumer-policy-progress.md).
- **Current feature:** read-only offline policy audit applies an explicit consumer
  policy to a verified in-memory aggregate snapshot. Reconcile its PR/head and
  final CI receipt before treating it as qualified; older runs do not prove it.
  It does not rerun models/scorers or claim source truth, freshness or authenticity.


- **Authority:** T2 `daily-driver` in `.agent-harness/tier.json`; push/merge only
  after the repository gate. No new owner-machine or runtime authority is implied.
- **Merged maintenance:** #78-#86 are integrated. #85 protects inputs and prior
  outputs during publication. #86 adds offline bundle receipts/verification and
  trusted pins without claiming authenticity or re-evaluating policy. Their exact
  heads, merge SHAs and CI are in [integrity progress](docs/evidence-integrity-progress.md).
- **Completed transport follow-up:** #87's command-file transport, alias checks
  and literal Action enforcement are merged and retain their prior CI receipt.
- **Prior capabilities:** #82 resolved #30 via opt-in byte limits and diagnostic
  failure exits. #83 added offline plans/request-bound replay; #84 qualified their
  installed-wheel path. [Prior receipts](docs/request-evidence-progress.md) are
  historical evidence, not CI for a later head. Existing defaults remain intact.
- **Release boundary:** all newer capabilities are unreleased main. The recorded
  GPL v0.2.0 publication on 2026-10-02 at 23:14:53 UTC and the approved `v0`
  transition target `d3e80877f0bdd309a049aba5dfdfd49ea032a1d9`. Historical MIT
  v0.1.0/v0.1.1/v0.1.2 tags, their objects, rights and attribution remain unchanged.
  See [the release receipt](docs/releases/v0.2.0.md); this pass moved no tags.
- **Owner decisions:** q-1/q-3 complete; q-2 deferred; q-4 requires two real users.
  q-5/q-6 approved the specific strict GPL v0.2.0 transition on 2026-10-02 at
  22:45:50 UTC, not future unattended releases. `HUMAN_TODO.md` remains authoritative.
- **Marketplace:** the last recorded receipt has Latest resolving to v0.2.0 but
  only v0.1.2 in the version chooser. Registration through the existing release
  editor remains an unexecuted UI follow-up, not a newly verified current UI fact.
  Stop for any new agreement/identity prompt; no new product decision is otherwise
  needed for that previously approved UI task.
- **Scope:** only #24 and #35 remain entry-gated in the last issue reconciliation.
  No live provider, private artifact, credential, runtime dependency or publication
  was introduced. Live PR-comment delivery and sdist installation remain unverified.
- **Numerics:** main's report hashes are checked across actual Python 3.11/3.13.
  Bundles include volatile invocation metadata and are not cross-run hashes.
  See [numerical limits](docs/numerical-reproducibility.md) for historical releases.

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
PRs #78-#90 are merged. Reconcile the consumer-policy audit follow-up and any later
review findings against its exact head, then use the final main-push receipt.
[Consumer-policy progress](docs/consumer-policy-progress.md) is the current handoff.
Do not repeat completed repairs or treat prior CI as proof for later code.

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
