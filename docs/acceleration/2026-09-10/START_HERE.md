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

## Reconstruct and preview

The decision and issue catalogs are inside the archive, not beside the checked-in
script. Run these commands from the **repository root**, using a new extraction
destination (the assembler refuses an existing non-empty destination):

```bash
python docs/acceleration/2026-09-10/archive/assemble_bundle.py --extract --destination .planning/acceleration-source
python docs/acceleration/2026-09-10/scripts/unbundle.py --repo . --bundle .planning/acceleration-source/llm-release-gate-acceleration-bundle --decisions docs/acceleration/2026-09-10/01-decisions/selected-decisions.example.json
```

Use the checked-in `scripts/unbundle.py`, not the historical copy inside the
reconstructed archive. `--bundle` is required and must point at the directory
containing `01-decisions/decision-catalog.json` and `02-roadmap/issue-catalog.json`.
The immutable archive is historical evidence and is not rewritten by this repair.

The example export is a **preview fixture, not current owner authorization**.
Use the owner's actual export for a real plan and reconcile every choice against
live repository state and `HUMAN_TODO.md`. A selected human-required option remains
visible as `blocked-human-decision` until its confirmation is literally JSON
`true`. A confirmation without a selected option does not grant authority.
Blockers propagate through all dependent tasks and retain their decision IDs.

The unbundler defaults to a dry run and writes nothing. Add `--scaffold` only to
write planning files under a child of `.planning`; `--force` retains that boundary.
It never edits product source, creates issues, or executes selected tasks.
