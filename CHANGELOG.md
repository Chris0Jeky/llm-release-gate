# Changelog

## Unreleased

- Add read-only consumer-policy audits of verified stored aggregates, with optional
  evidence/policy pins and separate original/new verdicts. Reject malformed direct
  evaluator inputs before computing policy outcomes.

- Field-match scorer v3 checks field presence separately from literal values; an
  absent field can no longer equal the legitimate string `<missing>`.

- Retain known response measurements after local processing failures, make partial
  token/cost totals unavailable, and attribute failures to their processing stage.

- Keep multiline workflow outputs literal, refuse command-file aliases to inputs
  or evidence, and enforce statuses as data rather than shell source.

- Add offline bundle integrity receipts, trusted-pin verification and an Action
  bundle-hash output, without reclassifying integrity as a passing gate.

- Protect loaded inputs and existing report bundles with staged publication,
  output-alias checks, cooperative locking and recoverable rollback.

- Add no-execution `plan` output and opt-in `sha256-v1` replay binding to the
  fully rendered request; binding errors cannot be relaxed by error-rate rules.
- Add CLI/Action binding requirements, report assurance disclosures, and a
  synthetic end-to-end replay/stale-evidence demo in the cross-Python CI matrix.

- Add opt-in per-file `--max-input-bytes` limits to gate/run and the Action,
  including transitive fixtures and an explicit manifest receipt.
- Add `run --fail-on-errors`, preserving diagnostic output and the default exit
  contract while allowing automation to reject any failed item with exit 2.

## 0.2.0 — 2026-10-02

This GPL release aligns the current source, package identity and Action release.
It retains the strict input contract; it does not restore legacy numeric name or
model coercion. Dataset/config names and model IDs must be non-empty strings.
Use `"123"` instead of `123` for a numeric-looking identifier. Invalid measured
usage, latency, pricing or threshold policy still fails closed.

- Contextual configuration diagnostics cover unreadable/non-regular files,
  malformed JSON/UTF-8, parser limits, fixture paths and oversized latency values.
- JSON-null schema scoring, report escaping and validation improvements since
  v0.1.2 are included; scorer/adapter identities describe those changes.
- Wheels and source archives include the GPL licence, relicensing record and
  retained MIT attribution, with fresh offline installation smoke in CI.
- Exit semantics remain 0 pass / 1 regression blocked / 2 could-not-run; the
  offline provider, threshold behavior and zero runtime dependencies remain.

### Licence and floating `v0`

v0.2.0 is GPL-3.0-only. Immutable v0.1.2 and earlier MIT releases retain their
previously granted rights and are never rewritten. The repository owner
explicitly approved publishing the strict GPL release and moving `v0` to it on
2026-10-02. This is a specific approved transition: floating `v0` consumers will
receive GPL source and the strict identifiers. Pin an immutable historical MIT
tag if that is the required licence, or pin an immutable current version/SHA.
The release ledger records publication and tag verification separately.
