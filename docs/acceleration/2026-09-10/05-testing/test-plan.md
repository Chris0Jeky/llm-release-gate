# Test and verification plan

## Testing philosophy

Preserve the repository's strongest existing practice: test the behaviour that can change a release verdict, not line coverage for its own sake. Every new schema, phase or disclosure policy needs a deliberately adversarial case.

## M0 suites

### Strict input and numeric semantics

- Reject NaN/Infinity/overflow floats and duplicate keys in every JSON input and fixture.
- Reject negative pricing and non-finite thresholds/usage/latency.
- Either enforce `currency == "USD"` in v0.x or make metric keys/rendering currency-aware.
- Validate nested document/schema/config shapes before an adapter/scorer indexes them.
- Reject unknown policy keys rather than accepting typoed constraints.

### Trusted extension contracts

- A scorer must emit exactly its declared metrics with a valid item-result shape.
- Duplicate provider/adapter/scorer registration fails deterministically.
- A provider result cannot contain invalid usage/latency types.
- The literal expected value `"<missing>"` remains distinguishable from an absent field.

### Report safety

- Fuzz table cells with `|`, newlines, backticks, HTML and Unicode.
- Neutralize accidental GitHub mentions in PR-facing text.
- Preserve raw content only under an explicit disclosure profile.
- Keep result hashes deterministic under redaction/truncation.

### Distribution/release

- Build sdist and wheel from a clean tree.
- Inspect both for all required licence notices.
- Install the wheel in a clean environment and run a green and deliberate-red gate.
- Prove the local Action source path without network installation.
- Run a Windows smoke lane and the hosted Action self-test.

## M1 suites

### Snapshot identity

- Same deterministic content produces the same snapshot hash in different directories and line-ending checkouts.
- Request change changes request hash.
- Response change changes response hash and snapshot hash.
- Volatile metadata does not alter deterministic evidence identity.
- Duplicate, missing, extra and reordered items follow documented semantics.

### Legacy migration

- v1 fixture without exact reconstructable request cannot be silently upgraded.
- Explicit legacy mode is visible in report/manifest and can be disallowed by policy.
- v2 fixture mismatch is exit 2, not a warning hidden in output.

### Paired comparison

Construct a table-driven matrix over:

- baseline/candidate success vs provider error;
- applicable vs inapplicable metric;
- pass vs fail;
- candidate-only threshold vs relative threshold;
- minimum paired coverage satisfied/breached.

Assert that relative metrics use only common valid/applicable pairs, while error/coverage and candidate floors evaluate the full candidate population.

### Disclosure profiles

Golden-test `local`, `private-ci` and `public-pr` outputs. Assertions should cover:

- raw output presence/absence;
- escaped Markdown;
- deterministic truncation boundary;
- original length and content hash;
- maximum report/comment byte budget;
- no timestamps or paths entering deterministic report identity.

## Property and mutation tests worth adding later

- Canonical hashing invariance/sensitivity properties.
- Threshold boundary monotonicity: worsening a metric cannot turn fail into pass.
- Mutation tests focused on inequality directions, unavailable branches and implicit error rules.
- Schema corpus tests generated from published JSON Schemas.

## Proving hierarchy

1. Narrow seam-specific tests while editing.
2. Cross-seam integration test for the slice.
3. Full suite and demos.
4. Package/Action tests at exact head.
5. Independent review of verdict semantics and report disclosure before release.
