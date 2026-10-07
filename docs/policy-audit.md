# Audit stored evidence against a consumer policy

`verify` answers whether a report bundle is internally consistent. `audit` adds a
separate question: do that bundle's stored aggregate values satisfy the threshold
policy supplied by this consumer? It does not rerun a model or a scorer, and it
does not replace the original report or its recorded verdict.

These commands are unreleased-main capabilities, not new behavior in existing
`v0`/`v0.2.0` installations. Historical bundles without an integrity receipt are
not implicitly upgraded or trusted.

## Example: require cost evidence that the producer did not gate

After `make demo-bound`, run:

```bash
python -m llm_release_gate audit \
  --bundle out/request-bound-replay \
  --thresholds examples/request-bound-replay/consumer-policy.json \
  --json
```

The synthetic producer's original quality/citation gate passes. The explicit
consumer policy also requires available cost below USD 0.10. The example has no
measured token usage or cost, so the consumer audit fails via the existing
`on_unavailable: fail` default. The receipt shows **recorded gate: pass** and
**consumer policy: fail**, without fabricating cost or calling a provider.

| Audit result | Exit |
|---|---:|
| Supplied policy passes against the validated stored aggregates | 0 |
| Supplied policy has a fail-level breach or fail-level unavailable result | 1 |
| Policy, evidence, metric representation or expected hash is invalid | 2 |

An explicitly different policy can also accept evidence whose original gate
failed. Both verdicts remain visible. This is not authority to bypass the
consumer's protected policy or an automatic promotion mechanism.

## Pin both evidence and policy across trust boundaries

```bash
python -m llm_release_gate audit \
  --bundle received-bundle --thresholds trusted-policy.json \
  --expected-result-hash "$TRUSTED_RESULT_HASH" \
  --expected-bundle-hash "$TRUSTED_BUNDLE_HASH" \
  --expected-policy-hash "$TRUSTED_POLICY_HASH" --json
```

All three flags are optional comparisons against independently supplied SHA-256
pins. A receipt records which comparisons were requested; their presence does not
prove that the caller obtained them from a trustworthy channel. A pin copied from
untrusted evidence supplies no independent assurance.

The policy hash covers **exact policy file bytes**, matching the `hash` command,
not reserialized JSON. Whitespace and physical line-ending changes therefore
change that pin even when policy meaning is unchanged. The report result hash and
invocation bundle hash retain their distinct [integrity contracts](bundle-verification.md).

The threshold JSON format is the existing `rules` format: metric, constraints,
optional fail/warn level and fail/warn/skip unavailable policy. Duplicate object
keys, non-finite numbers, unknown rule fields and empty rule lists are refused.
The implicit zero-error rule and explicit error-rule override behave exactly as
in `gate`; warn/skip remain deliberate consumer choices, not hidden exceptions.

## Snapshot and metric checks

The auditor uses the same in-memory report that the bundle reader verified. It
never verifies a path and then reopens a potentially different report. The
explicit policy is also parsed from one bounded regular-file snapshot. Stored
manifest paths are never followed. Policy and bundle inputs have the same default
16 MiB per-file limit, configurable with `--max-input-bytes N`. Final symlinks and
special files are refused. This is not a CPU budget or hostile-filesystem snapshot.

Before policy evaluation, report metric copies and run aggregate copies must
agree, including their key sets. The auditor requires the standard metric fields,
literal availability booleans, finite numeric values, non-negative integer counts,
and consistent rate values/counts. Both sides must use matching units/directions
and compatible available-value kinds. Unavailable values remain explicit nulls.
Arbitrary extension payloads are not copied into the audit's metric views.

The shared evaluator now also rejects malformed direct-API rules, non-boolean
availability flags, boolean/non-finite numeric values and non-representable
arithmetic observations. Previously, direct callers could receive a pass or a raw
exception for such malformed inputs. Valid ordinary evaluations and tolerances
are unchanged; exact large integer values are not coerced merely for validation.

## What the receipt does not establish

The versioned `lrg-policy-audit/1` receipt identifies the current evaluation
contract, tool, source result/bundle, explicit policy and per-rule outcomes. Its
`audit_hash` covers every field except itself, including which pins were checked.
The same bundle, policy bytes, evaluator and pin choices yield the same receipt
when moved to another location. New invocation bundle hashes intentionally change
that identity.

The result explicitly says source inputs were not verified, scores were not
recomputed, the original policy was not reproduced, and authenticity was not
verified. It checks declared metric consistency and evaluates the supplied policy;
it does not prove metric truth, producer identity, model execution, collection
freshness, original scoring correctness, or adequacy of the new policy. No raw
item response text is copied, but metric labels/notes and policy details can still
be sensitive. This is not a public-disclosure sanitizer.

The command writes only its receipt to stdout. It does not alter source evidence,
post comments, emit GitHub command-file outputs, create tasks, or promote a result.
The Python entry point is `llm_release_gate.audit.audit_bundle(directory, policy_path, ...)`.

## Proving checks

Tests cover stricter and looser policies, mismatched pins, duplicate keys, missing
metrics, contradictory aggregate copies, invalid counts/types, unavailable-policy
choices, relocation without original inputs, and mutation after snapshot capture.
All four public examples reproduce their policy verdict from their stored metrics.
Installed-wheel smoke and the actual Action test also demonstrate that the pinned
consumer policy refuses the otherwise passing synthetic bundle for unknown cost.
