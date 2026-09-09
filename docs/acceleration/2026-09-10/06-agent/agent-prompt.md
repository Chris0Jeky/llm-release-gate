# Copy/paste prompt for the in-repo agent

You are unbundling the `llm-release-gate` acceleration bundle into the live repository.

1. Treat live repository policy and evidence as authoritative. Read the repo's AGENTS/CLAUDE/tier/orchestrator/human-todo/next files in their required order, inspect Git/worktree/CI/PR/issue/tag/release state, and compare the current head to the bundle's analysed head `f9fe5adfd4c2d7e1ea5c982fd686a173e3e910cb`.
2. Read `06-agent/agent-manifest.json`, the owner's exported selected-decisions JSON, `02-roadmap/issue-catalog.json`, the risk register and relevant ADRs.
3. Never infer an unconfirmed human decision. In particular, do not move `v0`, choose/change the licence, publish, create secrets, persist user data or start hosted work without an explicit confirmed decision and applicable repo authority.
4. Generate a drift report and selected dependency-ordered workplan. Do not bulk-seed trigger-gated M3 work as active backlog.
5. Finish live failures/in-flight work first. Otherwise implement the smallest coherent unblocked slice, one PR at a time, with the narrow proving check followed by the full required gate. Reference snippets are starting points, not trusted patches.
6. Preserve: fail-closed behaviour, no fabricated measurements, deterministic path/timestamp-free report identity, honest counts/heuristic labels, stable exit codes, zero runtime dependencies unless explicitly approved, and exact-head release verification.
7. Update issue/docs/orchestration state only with observed evidence. At each stop report changed, verified, not verified, residual risk, human action and exact resume point.

Start by producing the live-state drift report and determining whether `I-001`/`I-002` remain the first safe slice.
