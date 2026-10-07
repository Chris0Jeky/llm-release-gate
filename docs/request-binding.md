# Request-bound offline replay

This feature is on unreleased main. Existing `@v0`/`v0.2.0` installations do not
acquire it until a separately qualified release is published.

## The boundary it adds

Legacy fake-provider fixtures are indexed by model and item ID. Changing the
rendered prompt while retaining those keys can replay the old response. This is
useful for synthetic demos but is not evidence that the new request was executed.

Opt-in **request binding** additionally compares every retrieved entry's
`request_sha256` with a fingerprint of the actual `ProviderRequest`. A different
system message, rendered prompt, model, parameters, item ID or metadata cannot
reuse a mismatched entry. Missing/malformed hashes, missing model/item entries,
and mismatches are configuration errors (exit 2), even with permissive
`errors.error_rate` thresholds. No new report or verdict is emitted.

This checks declared content identity, **not model execution or producer
identity**. Anyone able to edit fixtures can forge their hashes or responses.
It is not a signature, attestation, remote collector, full application-state
fingerprint, or proof of causality. Fields an application never puts into its
ProviderRequest cannot be covered. Keep CI policy and fixtures under an
appropriate review/protection boundary. A passing gate still means only that
its configured deterministic policy accepted the supplied evidence.

## Plan before collecting

From a checkout of current source after installation:

```bash
python -m llm_release_gate plan \
  --dataset examples/request-bound-replay/dataset.json \
  --config examples/request-bound-replay/candidate.json \
  --max-input-bytes 1048576 --out out/new-request-plan
```

`plan` uses the same task adapter as execution, but **does not construct a
provider, read fixtures, score outputs, or make model/network calls**. It works
when the configured fixture file does not exist yet. It validates rendering,
not provider availability, provider options, scorer policy or a release verdict.
Unknown providers can be named in a plan; that is not an execution capability.

The new `plan.json` contains `schema_version: lrg-request-plan/1`, tool and
adapter identities, dataset/config source hashes, provider, binding scheme,
ordered item IDs/request hashes, limitations, and its own `plan_hash`.
`plan_hash` covers every field except itself. Paths and timestamps are excluded.
Expected answers and source layout affect the enclosing input/plan identity,
not the individual request hash unless the adapter renders them into the request.
This permits rescoring the same evidence without pretending it was recollected.

No raw prompt, system text, response or parameter values are exported. However,
item IDs/provider names and hashes can still be sensitive, and hashes of
low-entropy inputs are guessable. This is not a redaction or public-disclosure
policy. Treat a plan accordingly before sharing it.

A plan file is created exclusively: an existing file, input file or symlink at
that name is never overwritten. Use a fresh output directory. A write failure
is exit 2; file existence alone never proves successful completion.

## Bind evidence at its producer

In the run config:

```json
"provider_options": {
  "fixtures": "fixtures/candidate.json",
  "request_binding": "sha256-v1"
}
```

Bound fixture containers must have exactly the supported string `"version": "1"`.
Each used entry needs a lowercase `sha256:` prefix followed by 64 hexadecimal
characters in `request_sha256`, alongside its usual text/usage/latency fields.
Error entries also need the request hash. A correctly bound error remains an
ordinary provider failure; existing error-rate policy still applies to it.
This feature does not silently change that policy or turn an outage into success.
Unused fixture entries are not a coverage guarantee; this is not a general
strict JSON/schema validator or a complete evidence-set importer.

At collection time, a producer using the same request representation calls
`llm_release_gate.requests.request_fingerprint(request)` and records the result
with the response to **that request**. Use the same rendering contract in the
application harness. Do not attach a new plan's hashes to unrelated old outputs:
that manufactures a matching declaration, not new evidence. The CLI deliberately
has no command that automatically stamps historical responses as newly bound.

## Require binding from CI, not only the candidate

Append `--require-request-binding` to `gate` or `run` to require the supported
fake-provider binding mode on every run config. This refuses a candidate that
removes the option. For the Action, supply:

```yaml
with:
  # Supply the standard dataset, baseline, candidate, scorers and thresholds.
  require-request-binding: "true"
  max-input-bytes: "1048576"
```

The Action accepts literal `"true"` or `"false"`, not shell expressions. Only
the built-in fake-provider mode is supported by this requirement. Future providers
must define their own reviewed evidence contracts, not claim compatibility merely
by naming an option. Keep the workflow's requirement itself protected; deleting
CI policy is outside this check.

Defaults remain unchanged: omitted binding preserves legacy replay; omitted
requirement does not demand it. Explicit unknown/null binding modes fail closed.
Bound mode appears in the report's provider identity and therefore in its result
hash. JSON, Markdown and HTML reports disclose its assurance limit. A selected
CLI requirement is also recorded in manifest execution options, alongside an
optional byte limit. It does not itself change accepted report bytes.

## Versioned fingerprint preimage

`sha256-v1` computes SHA-256 over UTF-8 bytes of this object, using the repository's
`hashing.canonical_json` encoding:

```json
{
  "schema_version": "lrg-provider-request/1",
  "model": "the request model",
  "system": "the request system text",
  "prompt": "the fully rendered prompt",
  "params": {},
  "item_id": "the request item ID",
  "metadata": {}
}
```

The encoder sorts object keys, uses separators `,` and `:`, emits Unicode without
ASCII escaping, rejects non-finite numbers, and adds no whitespace or terminal
newline. It is this Python encoding contract, **not RFC 8785/JCS**. Integral JSON
floats and integers (`1.0` versus `1`), signed zero, list order, exact Unicode
codepoints and escaped string content remain significant; key ordering does not.
The parsed number value, not its original lexical token, is encoded. Direct API
calls reject non-JSON containers/values, non-string keys and invalid UTF-8 strings.

Paths, timestamps, config display names, adapter version, expectations, scoring
rules and fixture bytes are not added to the request preimage. Adapter and source
identities live in the enclosing plan/report. A rendering change naturally changes
the request hash; a scoring-only change need not. Two fields with identical text
but different meanings do not alias because the field names and schema version
are included.

## Reproduce it offline

`make demo-bound` executes the committed synthetic example. It proves a valid
bound gate passes, a prompt mutation with the same fixtures is refused with exit 2,
and plans are output-location independent. It saves this demo's three reports, its plan and a small synthetic check receipt
for cross-version CI comparison.
The demo can be repeated; it replaces only its five named demo artifacts, not
arbitrary directories. The `plan` command itself remains non-overwriting.

`make ci` includes this check. Hosted Python 3.11 and 3.13 compare all four demos'
twelve reports plus the plan/check receipt byte for byte. Actual Action tests
cover a bound pass and refusal of legacy configs when binding is required.
Existing legacy green/red reports and hashes remain unchanged.
