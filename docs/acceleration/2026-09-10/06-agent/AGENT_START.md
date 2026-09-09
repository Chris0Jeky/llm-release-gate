# Agent start — unbundle and execute safely

## Authority

This bundle is a proposal based on `main` at `f9fe5adfd4c2d7e1ea5c982fd686a173e3e910cb`. Live Git, CI, issues, reviews, tags, releases, Marketplace state, `AGENTS.md`, `.agent-harness/tier.json`, `ORCHESTRATOR.md` and `HUMAN_TODO.md` outrank it.

Do not interpret reference snippets as already-tested patches. Reconcile them against current source and preserve repository invariants.

## Inputs

1. `01-decisions/decision-catalog.json` — all choices and option-to-task mapping.
2. Owner export from `interactive-decision-deck.html` — selected options and confirmation flags.
3. `02-roadmap/issue-catalog.json` — machine-readable tasks, dependencies, acceptance and tests.
4. `00-assessment/risk-register.json` — review findings.
5. `03-architecture/` and `04-implementation/` — proposed target and starting implementations.

## Cold-start sequence

1. Read the repository's own cold-start files in their specified order.
2. Refresh `git status`, worktrees, `origin/main`, open issues/PRs/reviews/checks, tags/releases and Marketplace state.
3. Compare current head with the bundle's analysed head. Record all drift.
4. Validate the owner decision export. A human decision is actionable only when `confirmed: true`.
5. Run `scripts/unbundle.py` in dry-run mode to produce the selected task plan.
6. Work an in-flight correctness/security failure first. Otherwise start with the smallest unblocked task in dependency order.

## Recommended first slice

Unless live state supersedes it:

- `I-001` fix `.claude/settings.json`: remove the `rg --pre` execution escape and scope `gh` reads.
- `I-002` synchronize runtime/harness facts and close issue #20 after measured verification.

Keep this separate from product/version/licence work.

## M0 sequence

After the first slice:

1. Resolve and record `D02`/`D03` before preparing a public release or moving `v0`.
2. Implement selected loader/verdict/report hardening as narrow PRs (`I-005`–`I-009`).
3. Add package/Action assurance (`I-010`–`I-013`).
4. Prove exact head and execute the selected release plan (`I-004`).

## M1 sequence

Use ADRs as proposals, then implement in dependency order:

`I-014 snapshot schema` → `I-015 request binding` + `I-016 pure compare` → `I-017 import/capture` → `I-018 paired populations` → schema/disclosure/atomic-write work.

Maintain a compatibility wrapper for the current `gate` command unless the confirmed decision says otherwise.

## Human blocks

Stop and write one clear question to `HUMAN_TODO.md` when a task requires:

- licence/tag strategy;
- publication or account setup;
- real provider/secret selection;
- persistence, retention or hosting;
- public/private disclosure policy;
- substantial product-boundary change.

Continue with other safe work rather than inventing an answer.

## PR completion template

```markdown
Changed:
Verified:
Not verified:
Verdict/schema compatibility:
Security/data disclosure impact:
Residual risk:
Human action:
Exact resume point:
```
