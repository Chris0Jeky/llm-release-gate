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

The next Action release is approved in q-5/q-6 below; qualification/publication
receipts remain separate agent-owned checks, reconciled on 2026-10-02.
Open other new questions only when live demand reaches an existing `NEXT.md` trigger.
In particular, a result store or hosted UI requires a privacy,
retention, and hosting decision before any user data is persisted.

## q-5 — GPL publication and floating `v0` — APPROVED 2026-10-02

The owner explicitly approved publishing the current GPL release and moving
`v0` to it at 22:45:50 UTC on 2026-10-02, after being told floating `v0`
consumers would receive the new GPL version. This selects D02/D03's GPL-latest
strategy. The current licence text is unchanged; historical MIT tags and their
attribution remain intact. Target version is v0.2.0, reflecting q-6's strict contract.

The decision supersedes the proposed patch-version plan:
[release plan](docs/acceleration/2026-09-10/02-roadmap/release-plan-v0.1.3.md) and
[ADR 0006](docs/acceleration/2026-09-10/03-architecture/adr/0006-release-licence-and-floating-tag.md).
ADR 0006 now records this approval and the specific transition exception.

- [x] Record the intended release and explicit D03 strategy before tagging or publishing.
- [ ] After the choice, verify the exact release head, package archives/clean install,
  Action self-test, licence notices, remote tags/release and Marketplace resolution.

Last verified publication before this release: `v0.1.2` and `v0` peel to
`5c3623587ef6b7d636f923021d10a238f5113df7` (MIT). v0.2.0 source is GPL-3.0-only;
the ledger records observed publication/tag state after qualification.

## q-6 — Strict identifiers — DECIDED 2026-10-02

The owner chose the simpler strict-identifier implementation and said there
are no users whose legacy coercion must be preserved. Numeric normalization
restoration was cancelled before any edit or commit; identifiers remain strings.
v0.2.0 signals the stricter pre-1.0 contract. Together with q-5, this is a
specific owner-approved exception to the default major-version/`v0` rule,
not a claim of backward compatibility or permission for future breaking aliases.
[Issue #65](https://github.com/Chris0Jeky/llm-release-gate/issues/65) records synthetic
full-gate reproductions: numeric dataset/config names and model IDs pass in published
v0.1.2 after explicit `str(...)` normalization, but current source rejects them with exit 2
after #42. The historical pre-version-bump probe compared two tool-version 0.1.2
trees; its string controls produced identical reports and hashes. v0.2.0 report
hashes change because the report embeds the tool version. This is separate from
fail-closed fixes for malformed policy or invalid measured data.

- [x] Record the intended input contract and release-version path.
- [ ] Requalify the final release head, retaining strict-name/model regressions
  and fail-closed measurement/policy tests.
