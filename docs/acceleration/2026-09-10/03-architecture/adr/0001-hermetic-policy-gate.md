# ADR 0001: Define llm-release-gate as a hermetic policy gate

- **Status:** Proposed
- **Date:** 2026-09-09
- **Decision owner:** Project owner
- **Related tasks:** I-014, I-016, I-017, I-023

## Context

The current project combines fixture-backed execution, scoring, threshold evaluation, and reporting. Its strongest capabilities are deterministic comparison, fail-closed policy, reproducible evidence identity, and concise CI enforcement. Its weakest adoption point is evidence production: real applications must currently author or record compatible fixtures outside the tool.

Competing evaluation systems already provide broad provider matrices, experiment tracking, hosted dashboards, and judge ecosystems. Rebuilding that surface would dilute the project and increase runtime and operational complexity.

## Decision

Position the product as a **hermetic policy gate over immutable LLM evaluation evidence**.

The core contract is:

1. accept versioned datasets/configuration and request-bound result evidence;
2. validate identity, completeness, and schema strictly;
3. score and compare deterministically;
4. apply explicit fail-closed release policy;
5. emit auditable machine and human reports;
6. exit with stable CI semantics.

Execution adapters, capture utilities, and importers remain optional evidence producers. A hosted platform is outside the core boundary.

## Consequences

### Positive

- Preserves the zero-service, CI-native character of the project.
- Creates a clear interoperability story with Promptfoo, DeepEval, Braintrust, custom harnesses, and real application tests.
- Concentrates engineering effort on verdict integrity rather than provider breadth.
- Allows offline and high-assurance use even when evidence was produced elsewhere.

### Negative

- “One Action and done” onboarding remains unrealistic until a capture/import path exists.
- Users must understand the distinction between evidence production and release policy.
- A canonical snapshot contract becomes a public compatibility surface.

## Rejected alternatives

- **Provider-first evaluation framework:** too broad and duplicates established tools.
- **Hosted release-management platform now:** introduces persistence, privacy, tenancy, authentication, and cost before demand.
- **Replay-only tool:** deterministic, but cannot honestly prove that a changed prompt/config produced the stored output.

## Review trigger

Revisit only if multiple users demand the gate itself to own live execution and cannot use a capture/import boundary without excessive integration code.
