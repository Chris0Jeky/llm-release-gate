# Start here — llm-release-gate acceleration bundle

This material is a proposal derived from repository state at `f9fe5adfd4c2d7e1ea5c982fd686a173e3e910cb`. Reconcile it with live Git, CI, issues, reviews, releases, `AGENTS.md`, `.agent-harness/tier.json`, `ORCHESTRATOR.md` and `HUMAN_TODO.md` before editing.

## Understand

Read:

- `00-assessment/risk-register.json`
- `00-assessment/source-index.md`
- the complete repository review reconstructed from `archive/`

## Decide

Use:

- `01-decisions/human-decision-worksheet.md`
- the interactive decision deck and machine-readable decision catalog reconstructed from `archive/`

Decision `D03` intentionally requires explicit owner confirmation because it governs the licence/floating-`v0` transition.

## Execute

Read `06-agent/AGENT_START.md`, then use the issue catalog and implementation references in dependency order. Work the smallest coherent, verifiable slice. Do not treat trigger-gated horizon work as an active backlog merely because it is documented here.

To reconstruct and optionally extract the complete bundle:

```bash
python archive/assemble_bundle.py --extract
```
