# HUMAN_TODO — llm-release-gate

Only actions that an agent cannot safely complete belong here (accounts, agreements,
identity, spending, or a material product choice). Agents may check an item off only when
completion is directly verified; never infer a human decision. The current release stage is
in [ORCHESTRATOR.md](ORCHESTRATOR.md).

## q-1 — Published Action reference — DECIDED 2026-08-02

Owner decision: publish the Action from the renamed public repository as
`Chris0Jeky/llm-release-gate@v0`.

- [x] Repository renamed and canonical reference selected: `Chris0Jeky/llm-release-gate@v0`.
- [x] Annotated `v0.1.0` and initial `v0` tags both verified at `0e0f480`; the public
  [v0.1.0 GitHub release](https://github.com/Chris0Jeky/llm-release-gate/releases/tag/v0.1.0)
  is published.
- [x] Annotated `v0.1.1` remains immutable at `5514019`; the public
  [v0.1.1 GitHub release](https://github.com/Chris0Jeky/llm-release-gate/releases/tag/v0.1.1)
  is published.
- [x] Annotated `v0.1.2` and the current `v0` compatibility tag both verified at `5c36235`;
  the public [v0.1.2 GitHub release](https://github.com/Chris0Jeky/llm-release-gate/releases/tag/v0.1.2)
  is published.

The agent-owned initial release is complete. `v0` may move only with a later reviewed,
verified 0.x release; it is never an unattended automation target.

## q-2 — PyPI — DEFERRED BY OWNER 2026-08-02

Do not publish to PyPI, create a token, or add a publishing workflow until a real user asks
for `pip install`. At that point re-check name availability and use PyPI Trusted Publishing
(short-lived GitHub OIDC), not a long-lived API token. This is a dormant trigger, not an
active action item.

## q-3 — GitHub Marketplace — COMPLETED 2026-08-02

The owner completed the Marketplace workflow. The public
[llm-release-gate Marketplace listing](https://github.com/marketplace/actions/llm-release-gate)
is live at `v0.1.2` with **Continuous integration** and **Code quality** categories.

- [x] Owner-only Marketplace agreement/identity and category selection completed; public
  listing directly verified 2026-08-02.

## q-4 — Real provider adapter — WAIT FOR TWO REAL USER REQUESTS

Only the offline `fake` replay provider exists. Do not choose a provider, create secrets, or
add a provider matrix until `NEXT.md`'s two-user trigger is met. Then the owner chooses the
first requested provider and secret delivery path, and `.agent-harness/tier.json` receives a
fresh `sensitive_data` review. Keys remain environment-only and are never committed.

## Future owner gates

The next Action release is blocked on q-5 and q-6 below, reconciled on 2026-10-02.
Open other new questions only when live demand reaches an existing `NEXT.md` trigger.
In particular, a result store or hosted UI requires a privacy,
retention, and hosting decision before any user data is persisted.

## q-5 — Next Action release and licence/floating-tag strategy — OWNER DECISION REQUIRED

Which release and licence/floating-tag strategy should be used for current GPL source?
The existing acceleration bundle requires explicit D02/D03 decisions before publication:
[release plan](docs/acceleration/2026-09-10/02-roadmap/release-plan-v0.1.3.md) and
[ADR 0006](docs/acceleration/2026-09-10/03-architecture/adr/0006-release-licence-and-floating-tag.md).
The ADR remains Proposed with no choice recorded. Its options include GPL with an explicit
floating-tag transition, GPL with `v0` frozen on MIT, a permissive licence, or dual licensing;
an agent must not select a licence strategy. Any `v0` movement also requires q-6 compatibility.

- [ ] Record the intended release and explicit D03 strategy before tagging or publishing.
- [ ] After the choice, verify the exact release head, package archives/clean install,
  Action self-test, licence notices, remote tags/release and Marketplace resolution.

Observed state: published `v0.1.2` and `v0` still peel to
`5c3623587ef6b7d636f923021d10a238f5113df7` (MIT). Current source is GPL-3.0-only but
still reports package version `0.1.2`. General merge/deploy authorization does not select
the licence received by floating-tag consumers. No release or tag was changed by this audit.

## q-6 — Released input compatibility — OWNER DECISION REQUIRED

Preserve harmless released name/model normalization for a compatible maintenance release,
or retain the narrowed schema and use the major-version path while leaving `v0` untouched?
[Issue #65](https://github.com/Chris0Jeky/llm-release-gate/issues/65) records synthetic
full-gate reproductions: numeric dataset/config names and model IDs pass in published
v0.1.2 after explicit `str(...)` normalization, but current source rejects them with exit 2
after #42. String controls produce identical reports and hashes. This is separate from
fail-closed fixes for malformed policy or invalid measured data.

- [ ] Record the intended input contract and release-version path.
- [ ] Add regressions for that contract and requalify the final release head; repository
  policy treats breaking input schemas as a major-version event and forbids moving `v0`.
