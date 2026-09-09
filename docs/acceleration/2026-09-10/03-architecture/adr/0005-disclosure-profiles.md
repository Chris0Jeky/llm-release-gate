# ADR 0005: Make report disclosure an explicit profile

- **Status:** Proposed; owner confirmation required for defaults
- **Date:** 2026-09-09
- **Related tasks:** I-008, I-013, I-021, I-022

## Context

Current JSON and HTML reports can contain complete model outputs, item IDs, score details, and provider errors. This is useful locally but can disclose prompts, retrieved documents, customer text, secrets echoed by a model, or operational details when uploaded to CI or posted on public pull requests.

## Decision

Introduce three deterministic profiles:

### `public-pr`

- no raw outputs;
- bounded failing-item IDs or stable pseudonyms;
- provider failures reduced to stable classes/codes;
- Markdown table escaping and mention neutralisation;
- deterministic truncation and size limits;
- hashes and aggregate counts retained.

### `private-ci`

- selected failing outputs may be included after deterministic redaction/truncation;
- sensitive field paths configurable;
- no credentials, raw headers, or unrestricted provider exceptions;
- detailed artifacts uploaded only under an approved retention policy.

### `local`

- full diagnostics and outputs permitted;
- credentials still excluded;
- local paths may live in the volatile manifest, never the reproducible report hash.

## Consequences

- Safer public defaults and clearer operational guidance.
- Report bytes differ by profile; the profile and redaction-policy version must be part of report identity.
- Redaction cannot guarantee removal of arbitrary secrets without a threat model; public mode therefore excludes raw text rather than relying solely on pattern filtering.

## Open owner decision

Choose the default profile for the GitHub Action and whether public repositories may upload private-detail artifacts at all.
