# llm-release-gate acceleration review

This directory contains the repository review and acceleration package prepared against `main` at `f9fe5adfd4c2d7e1ea5c982fd686a173e3e910cb`.

## Start here

1. Review the findings and evidence in `00-assessment/`.
2. Work through the owner choices in `01-decisions/`.
3. Use `02-roadmap/` for the 33-task backlog, dependencies and proposed v0.1.3 release sequence.
4. Treat the ADRs in `03-architecture/adr/` as proposals until explicitly accepted.
5. Use `04-implementation/` and `05-testing/` as implementation and verification references.
6. Give `06-agent/AGENT_START.md` plus the selected decision export to the in-repo agent.

The complete original review, interactive HTML decision deck, decision catalog, issue catalog, issue seeds and local acceleration bundle are preserved in `archive/`. Run:

```bash
python docs/acceleration/2026-09-10/archive/assemble_bundle.py --extract
```

The script verifies the reconstructed archive before extracting it.

## Scope

This pull request contains planning and reference material only. It does not modify runtime source, the composite GitHub Action, CI behavior, tags, releases or Marketplace state. Live GitHub state and the repository's own authority files outrank this snapshot.
