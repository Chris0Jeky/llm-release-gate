# Verify a report bundle offline

This capability is on unreleased main. It does not change the published `v0` or
`v0.2.0` tags. The report schema and existing deterministic result hashes remain
unchanged; new gate manifests add a versioned `bundle_integrity` receipt.

## Verify the evidence, then choose whether its verdict is acceptable

From current installed source, after running a gate:

```bash
python -m llm_release_gate verify --bundle out/my-gate --json
```

The command reads exactly `report.json`, `report.md`, `report.html`, and
`manifest.json` from that directory. It does not run a provider, evaluate source
inputs, recompute scores or thresholds, or emit GitHub output/summary commands.
Paths stored inside the manifest are descriptive data and are never followed.
A copied bundle can be verified without its original checkout or input files.

| Result | Exit |
|---|---:|
| Internally consistent bundle, whether its recorded gate passed or failed | 0 |
| Internally consistent bundle recording failure, with `--require-pass` | 1 |
| Missing, malformed, changed, unsupported, locked, or pin-mismatched evidence | 2 |

Thus `integrity: verified` is **not** a new passing gate verdict. The JSON result
separately reports `gate_verdict`, which is the recorded result, and explicitly
sets `input_sources_verified`, `policy_recomputed`, and `authenticity_verified`
to false. `--require-pass` inspects that recorded verdict; it does not re-evaluate
whether the chosen policy was adequate.

## Use a trusted pin across a transfer boundary

For a consumer receiving artifacts from another job, preserve a pin in a trusted
channel independent of those artifacts. Pass one or both pins:

```bash
python -m llm_release_gate verify --bundle received-gate \
  --expected-result-hash "$TRUSTED_RESULT_HASH" \
  --expected-bundle-hash "$TRUSTED_BUNDLE_HASH" \
  --require-pass --json
```

Both pins use lowercase `sha256:` followed by 64 hexadecimal digits.
`external_pins` in the JSON response records which comparisons were requested.
The Action exposes `bundle-hash` in addition to the existing `result-hash`.
Protect the workflow and its outputs; reading an expected pin from the very
bundle being checked supplies no independent trust.

- **Result hash** identifies the canonical report content. It remains stable
  across equivalent reruns and does not include invocation paths or timestamps.
- **Bundle hash** identifies the three exact report byte streams and the
  canonical invocation manifest. It includes the manifest's timestamp, stored
  paths and execution options, so it normally changes on a new invocation.
  Moving an existing bundle without editing its contents preserves this hash.

Someone who controls every file can construct a new self-consistent bundle.
Only a separately trusted pin detects that complete rewrite. Even a trusted
pin authenticates content relative to that pin, not the model, producer, source
truth, collection time, policy adequacy, or real execution. This command is not
a signature verifier, HTML sanitizer, archival freshness check, or remote trust
service. Do not open untrusted HTML merely because an unpinned check passed.

## Receipt contract and validation

The `bundle_integrity` object uses `schema_version: lrg-report-bundle/1` and has
exactly these other fields:

- `result_hash`: the report's canonical content hash, also present in the manifest;
- `manifest_sha256`: canonical hash of every manifest field except `bundle_integrity`;
- `files`: exactly the three report filenames, each with raw-byte `sha256` and
  integer `size_bytes`;
- `bundle_hash`: canonical hash of the receipt excluding `bundle_hash` itself.

Canonical hashing uses this repository's UTF-8 Python JSON encoding, not JCS.
The manifest may be reformatted without changing its canonical hash. The three
report byte streams are checked exactly, so even an added whitespace byte is a
change. JSON decoding refuses duplicate keys, non-finite values and invalid
UTF-8. Unknown receipt fields and versions are refused rather than guessed.
Manifests without this receipt are explicitly unsupported, not silently trusted.

Verification recomputes the report hash and checks header consistency: tool and
schema identities, rule-verdict counts and overall recorded verdict, required
input-hash declarations, and provider identities shared by report and manifest.
It checks declared content consistency, **not a complete semantic re-evaluation**
of items, metrics, score calculations, threshold execution or rendered prose.
The manifest's input hashes are declarations until separately checked against
source bytes; this command does not do that.

## Filesystem and resource limits

A publication lock, final symlink, directory or special-file artifact is refused.
The verifier checks opened descriptors and file identity/size/mtime before and
after reads, then rechecks the bundle. It never clears a lock or changes evidence.
These checks catch ordinary concurrent changes but do not provide an atomic
filesystem snapshot against a hostile external writer. Prefer a quiescent copied
bundle in a directory the consumer controls. See [output safety](output-safety.md).

Reads have a default **16 MiB raw-byte limit per artifact**. Override it with
`--max-input-bytes N` (a positive integer) when a known bundle needs more room.
This is not a total process-memory, JSON-object, CPU or elapsed-time limit.
Direct library callers use `llm_release_gate.bundles.verify_bundle(directory, ...)`
with the same default; the shared byte-limit scope also accepts `None` for an
explicit unlimited library call, which is not exposed as a verifier CLI default.

`make verify-demo` generates and verifies all four demos, including the deliberately
failed gate. `make ci` includes it. Cross-Python CI still compares only deterministic
reports/plans/receipts; invocation manifests and their bundle hashes are not
expected to match between jobs. The Action self-test additionally verifies its
actual bound bundle against the separately emitted Action output pins. Fresh-wheel
acceptance proves the verifier runs from installed code and refuses a changed report.
