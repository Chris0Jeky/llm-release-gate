# ADR 0006: Resolve the GPL release and floating `v0` transition explicitly

- **Status:** Accepted 2026-10-02; owner approved GPL publication and moving `v0`
- **Date:** 2026-09-09
- **Decision owner:** Repository owner
- **Related tasks:** I-003, I-004

## Context

The immutable v0.1.2 release and current floating `v0` compatibility tag point to an MIT-licensed commit. Current `main` is GPL-3.0-only but still reports package version 0.1.2. Publishing a GPL patch and moving `v0` would materially change the licence received by floating-tag consumers. Earlier MIT grants remain valid.

## Decision recorded

On 2026-10-02 at 22:45:50 UTC, the owner explicitly approved publishing the
current GPL release and moving `v0` to it, after being told floating consumers
would resolve to the new GPL version. The owner also selected strict identifiers
and cancelled compatibility restoration because there are no users to preserve
it for. Release v0.2.0 reflects this pre-1.0 input-contract transition, without
claiming backward compatibility. This is a specific approved exception to the
default breaking-change/major-version and `v0` rules, not a future blanket waiver.

Current GPL licence text and historical MIT attribution are unchanged; immutable
MIT version tags/releases remain untouched. Publication/tag verification is
recorded separately in the release ledger after all acceptance checks pass.

## Historical options

Select and document one strategy before tagging or moving `v0`:

1. **GPL latest with explicit notice** — publish v0.1.3 and move `v0`; prominently disclose the transition and preserve immutable MIT pins.
2. **Freeze `v0` on MIT** — publish GPL v0.1.3 without moving `v0` until a new compatibility channel is announced.
3. **Return to a permissive licence** — relicense current work under MIT or Apache-2.0 to reduce adoption friction.
4. **Dual licence** — retain GPL distribution and offer a commercial licence after contributor/IP governance is established.

## Approval boundary

The owner selected GPL latest with explicit notice. That approval covers this
strict v0.2.0 release and `v0` movement only; it does not authorize relicensing,
PyPI publication, new hosting, or rewriting an immutable release/tag.

## Required release properties once selected

- one version identifies one source/package/licence state;
- immutable version tags are never rewritten;
- release notes state the applicable licence and compatibility-tag behaviour;
- exact-head CI, package installation, Action self-test, archive licence contents, tag peeling, release, and Marketplace state are verified;
- `ORCHESTRATOR.md` and `HUMAN_TODO.md` record observed completion.
