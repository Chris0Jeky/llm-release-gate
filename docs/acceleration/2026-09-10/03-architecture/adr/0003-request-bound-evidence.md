# ADR 0003: Bind every result item to the exact evaluated request

- **Status:** Proposed
- **Date:** 2026-09-09
- **Related tasks:** I-014, I-015, I-020

## Context

The fake provider currently indexes responses by `(model, item_id)`. A prompt, system message, parameters, documents, or adapter convention can change while an old fixture still resolves. The resulting verdict may claim to evaluate a candidate request that never produced the stored output.

## Decision

Every planned item receives a deterministic `request_sha256` over the exact semantic request:

```json
{
  "schema_version": "1",
  "adapter": {"name": "rag", "version": "2"},
  "item_id": "refund-policy-1",
  "model": "model-name",
  "system": "...",
  "prompt": "...",
  "params": {"temperature": 0}
}
```

Every successful or failed result item must carry that hash. Snapshot validation rejects:

- missing request hashes;
- hashes absent from the referenced plan;
- duplicate item IDs or request hashes;
- mismatched dataset/config/adapter identities;
- extra or missing expected items unless an explicit completeness policy permits them.

A mismatch is a configuration/evidence error and exits 2. It is not a warning and must never become a passing release verdict.

## Hash semantics

- Use canonical JSON: sorted keys, compact separators, UTF-8, finite values only.
- Exclude paths, timestamps, CI URLs, and other volatile provenance.
- Keep request identity separate from higher-level config identity so non-semantic metadata changes do not invalidate every item unnecessarily.

## Legacy migration

Fixture v1 can be labelled `legacy-unbound`; migration must not invent request hashes. Normal trusted mode rejects unbound evidence. A temporary explicit compatibility flag may allow legacy examples, but reports must disclose that the evidence was not request-bound.
