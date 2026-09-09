# ADR 0006: Resolve the GPL release and floating `v0` transition explicitly

- **Status:** Proposed; **no decision recorded**
- **Date:** 2026-09-09
- **Decision owner:** Repository owner
- **Related tasks:** I-003, I-004

## Context

The immutable v0.1.2 release and current floating `v0` compatibility tag point to an MIT-licensed commit. Current `main` is GPL-3.0-only but still reports package version 0.1.2. Publishing a GPL patch and moving `v0` would materially change the licence received by floating-tag consumers. Earlier MIT grants remain valid.

## Decision required

Select and document one strategy before tagging or moving `v0`:

1. **GPL latest with explicit notice** — publish v0.1.3 and move `v0`; prominently disclose the transition and preserve immutable MIT pins.
2. **Freeze `v0` on MIT** — publish GPL v0.1.3 without moving `v0` until a new compatibility channel is announced.
3. **Return to a permissive licence** — relicense current work under MIT or Apache-2.0 to reduce adoption friction.
4. **Dual licence** — retain GPL distribution and offer a commercial licence after contributor/IP governance is established.

## Non-decision

This ADR deliberately does not select an option. An agent may prepare evidence and release mechanics but must not choose the licence, publish, or move the floating tag without explicit owner confirmation.

## Required release properties once selected

- one version identifies one source/package/licence state;
- immutable version tags are never rewritten;
- release notes state the applicable licence and compatibility-tag behaviour;
- exact-head CI, package installation, Action self-test, archive licence contents, tag peeling, release, and Marketplace state are verified;
- `ORCHESTRATOR.md` and `HUMAN_TODO.md` record observed completion.
