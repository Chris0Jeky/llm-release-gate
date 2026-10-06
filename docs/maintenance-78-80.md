# Maintenance receipt: PRs #78-#80

## Source and qualification

The uploaded source archive was reconciled with live main
`7e7176c40dbd47baa22e53ebe173a353158c6bf7`. Its complete Git tree matched
`788f732068afabef2dbc2f1c5713892381de8653`; the archive comment alone was not
used as proof. All writes used GitHub branches and draft PRs, with exact source-tree
comparisons before publication and exact-head CI before merge.

| Change | Qualified head | Merge | Hosted CI | Local full-suite count |
|---|---|---|---|---:|
| [#78: stable aggregation](https://github.com/Chris0Jeky/llm-release-gate/pull/78) | `cea040f429b0782025493c89c9684929383284a2` | `837a852f838ade41e77b930f88fb3baf735372f7` | [37545705753](https://github.com/Chris0Jeky/llm-release-gate/actions/runs/37545705753) | 381 |
| [#79: unbundler contracts](https://github.com/Chris0Jeky/llm-release-gate/pull/79) | `2869f0e5674dd0c9b4f02161111ac3f7c615672e` | `70ee41ccdd8b1f06e47ada51357ca2d1e8edebb5` | [37546706975](https://github.com/Chris0Jeky/llm-release-gate/actions/runs/37546706975) | 403 |
| [#80: permission rules](https://github.com/Chris0Jeky/llm-release-gate/pull/80) | `2d213c0bb72eeccbfc2d4b3a965657dfacb84ae7` | `8bbee7a8dee2f98b6274d13c7bee9fbdc1b2df54` | [37547066399](https://github.com/Chris0Jeky/llm-release-gate/actions/runs/37547066399) | 407 |

Each hosted run passed both Python 3.11/3.13 lanes, package and fresh-wheel
acceptance, the Action green/red self-test, and all nine cross-version report
comparisons. Reviews were documented maintenance self-reviews, not independent
reviewer approvals. No external findings were pending at those merges.

The original isolated baseline passed 375 tests. The shared interpreter initially
failed six resource-limited subprocess tests before importing the CLI; a clean
task-owned interpreter passed the unchanged baseline. The fixes did not weaken
those tests or remove their limits. New regressions were observed failing before
implementation. `make ci` retained both passing demos and the deliberately blocked
regression demo.

The actual acceleration archive was reconstructed and checksum-verified. The
repaired dry-run retained 26 selected/dependency tasks, including 20 human-blocked
tasks. Historical archive shards were not rewritten, and the example decision
export was not treated as current owner authorization.

## Artifact-intake follow-up

The #78 comparison job passed but its v5 downloader logged a Node 20 deprecation
warning. The follow-up pins official `actions/download-artifact` v8.0.1 to
`3e5f45b2cfb9172054b4087a40e8e0b5a5461e7c`, whose action manifest declares Node 24,
and explicitly sets `digest-mismatch: error` for both same-run downloads. No new
token, cross-repository intake, write permission, or continue-on-error bypass is
introduced. Its own exact-head CI must qualify the runtime change; the three
older receipts above are not evidence for a later head.

## Remaining work and limits

- [#30 reconciliation](https://github.com/Chris0Jeky/llm-release-gate/issues/30#issuecomment-6027447488): input bytes remain uncapped after regular-file validation. Diagnostic `run` writes records and returns zero even if every item failed; it is not a release verdict. The implicit error gate remains overridable by an explicit rule. Changes need deliberate compatibility decisions; use `gate` for enforcement.
- [#35 reconciliation](https://github.com/Chris0Jeky/llm-release-gate/issues/35#issuecomment-6027449878): huge fixture latency already fails with a named exit-2 error. Mixed non-finite percentile handling is still explicitly deferred to the first real-provider boundary; do not silently hide invalid samples or coverage.
- [#24 readiness checklist](https://github.com/Chris0Jeky/llm-release-gate/issues/24#issuecomment-6027453765): qualify approved pinned producer artifacts and schema stability before adding a report-only consumer. A declared digest is not independently verified without its preimage. No source-private artifacts were copied here and no advisory-to-merge authority was added.

The permission repair proves static rule removal, not actual Claude runtime
matching or complete sandboxing. User/global settings and owner-machine state
were not changed. Real providers, live PR-comment delivery, PyPI and Marketplace
UI actions were not qualified by this work. No release tag was moved: these
maintenance fixes are on main, not a claim of a new published release. Historical
release hashes still require their historical interpreter context; see
[numerical reproducibility](numerical-reproducibility.md).
