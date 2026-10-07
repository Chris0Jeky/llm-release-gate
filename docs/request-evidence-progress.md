# Request-evidence product progress

These additive capabilities are on main, not a new tagged release. No provider
credentials, private producer artifacts, runtime dependencies, publication
settings or existing release tags were changed.

## Merged feature slices

| Slice | Qualified PR head | Merge | Hosted PR CI | Full local suite |
|---|---|---|---|---:|
| [#82: automation controls](https://github.com/Chris0Jeky/llm-release-gate/pull/82) | `ec5603f006c8caa824fb34b99535da2730a05c7a` | `827c050e987b6b90009d6efc51528c61c21a25d7` | [37554304564](https://github.com/Chris0Jeky/llm-release-gate/actions/runs/37554304564) | 438 |
| [#83: request-bound replay](https://github.com/Chris0Jeky/llm-release-gate/pull/83) | `17b5fb481f1bce3e7276678a244f1c8937f138fa` | `7a343351d55427d010f288016d12fff2a72d79fc` | [37556565750](https://github.com/Chris0Jeky/llm-release-gate/actions/runs/37556565750) | 502 |

Both PRs passed their own Python 3.11/3.13, package, Action and deterministic
artifact comparison jobs before expected-head-guarded merges. The old three
demo hashes are unchanged. The new example is explicitly hand-authored synthetic
evidence, with unmeasured tokens, latency and cost left unavailable.

#83 compares twelve JSON/Markdown/HTML reports plus the request plan and synthetic
binding-check receipt across both Python versions. The actual Action self-test
proves legacy green, deliberate red, byte-limit refusal, bound acceptance and
refusal of unbound configurations under an independent binding requirement.

Reviews were self-reviews, not independent approvals. Exact source-tree hashes
were compared before publication. Red-before-green rounds and compatibility
checks are recorded in each PR, not inferred from test counts alone.

## Installed-feature acceptance follow-up

The follow-up extends `scripts/verify_dist.py --smoke` rather than changing product
semantics. Its isolated installed-wheel subprocesses exercise plan-before-evidence,
non-overwrite, bound replay, stale-evidence refusal, requirement downgrade refusal,
input caps and diagnostic failure output. Six new verifier tests include mutation
probes for incorrect request/binding identities, misleading generic failures,
overwritten plans and missing diagnostics. All six failed before implementation;
the complete local suite then passed 508 tests and all four demo checks.

For a real artifact check, the #83 CI package ZIP was retrieved through the GitHub
connector, not rebuilt from the working tree. Artifact `11454692606` is associated
with the qualified #83 head. Verified SHA-256 values:

- artifact ZIP: `2d1651e6b3e04289ebc0d0e6ce7d99ee85d9c53fb51a211c5da54737430d95d7`
- wheel: `2434b86a8c869d3a308e9227c485cef852f8e6b27a26084bbbeb28030eea343c`
- source archive: `988aeb6eda8ba6fa524afc3a3bfee49dc91fbfd80a19d867f7f1b8b171ab325a`

That wheel passed the expanded verifier after an offline, no-dependency install
into a fresh virtual environment. All CLI subprocesses use `-I`, with Python
path/home and GitHub output environment variables removed; import identity must
resolve inside the environment. The source checkout supplies public synthetic
inputs, not executable product imports. This does not claim an sdist installation
smoke or a newly published package. The follow-up PR's own exact-head hosted CI
and final merge receipt remain authoritative for its later tree.

## Remaining scope

[#30](https://github.com/Chris0Jeky/llm-release-gate/issues/30) is closed through
the opt-in controls and previously merged repairs. Default unlimited input,
default diagnostic exit 0 and explicit error-rule override remain deliberate
compatibility choices, not unadvertised behavior changes.

[#24](https://github.com/Chris0Jeky/llm-release-gate/issues/24) still requires an
approved pinned producer fixture pair and schema qualification before an HQ
report-only consumer. This request-bound fake replay is not that importer.
[#35](https://github.com/Chris0Jeky/llm-release-gate/issues/35) retains its first-real-
provider latency-boundary trigger; no live provider was introduced.

Request hashes prove consistency of supplied content, not authenticity or model
execution. Protect the CI policy itself and never re-stamp unrelated old outputs
as newly collected evidence. See [binding](request-binding.md) and
[automation controls](automation-controls.md) for the exact contracts and limits.
