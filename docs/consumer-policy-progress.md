# Consumer-policy maintenance checkpoint

The pass started at main `3b3690227d76aa7f4f7b72ac5666bcaf19813576`, including
independently merged #88. Supplied source and prior patches were reconciled to
its exact tree `545a755d2d623090a0272a80e64276bc88def3e9`; 637 baseline tests passed.

| Merged repair | Qualified head | Merge | PR CI | Full suite |
|---|---|---|---|---:|
| #89 post-response evidence | `bdd19c8971e8db0820cab91ccd6d1e8f7171829c` | `19eec7b159d4286bd8dc215d0660bf749a8dcf2b` | `37688318990` | 656 |
| #90 field-match v3 | `4cde166174afb0a3d3282daf63270fccfb61e746` | `683a159b0ebad65a1e7edb162eecbb96ee940c48` | `37689086923` | 669 |

Both fixes passed their exact-head hosted matrix, package, Action and deterministic
comparison jobs before guarded merges. Reviews were self-reviews, not independent
approvals. The two original #38 review findings received implementation/evidence
replies. No new release tag or provider was introduced.

#89 preserves known response data after local failures and makes consumption totals
unavailable rather than reporting understated surviving-item sums. Its real replay
cost-overflow reproducer originally returned green under permissive error rules.
#90 removes the field-match string-sentinel false positive and increments the scorer
identity. The extraction demo hash changes to `7fae5b8813cd6a91bb900eba7dbde3d59a507bf89bddda0a1ff1ac41760fa024`;
its verdict and the other three examples' hashes/verdicts are unchanged. Historical
release measurements are not rewritten.

## Consumer-policy audit follow-up

The new read-only `audit` command applies an explicit, optionally pinned policy to
one verified stored-aggregate snapshot. It checks repeated metric representations
and shape/count consistency, preserves the producer's original verdict, and emits
separate consumer outcomes. The existing integrity-only `verify` contract remains.
No model, scorer, stored source path, raw response export or promotion is involved.

The evaluator-input regression round had 28 failures and two controls passing before
repair; 31 initial audit tests failed before implementation. Installed-smoke and
hosted wiring regressions also failed before their integration changes. Final local
`make ci` passed 738 tests and all demo/bundle checks. The audit PR's own exact-head
hosted validation and post-merge receipt remain necessary; prior PR runs are not
substitutes. Source tree equality is checked before publication.

The example consumer policy requires cost evidence. It returns a failed audit for
the synthetic bound bundle despite that bundle's recorded pass, because its cost is
unavailable. The inverse is possible with an intentionally different policy; the
receipt always distinguishes these decisions. Pin channels and policy adequacy are
the consumer's responsibility, not claims made by an unpinned audit.

## Resume boundaries

Read [processing failures](processing-failures.md), [field-match v3](field-match-v3.md)
and [policy audit](policy-audit.md). Refresh live main, issues, PRs, review threads
and exact-head CI, then finish or reuse the policy-audit PR receipt. Do not redo
completed #78-#90 maintenance. #24's producer-artifact/schema qualification and #35's
first-real-provider boundary are unchanged; neither is completed by this audit.

These changes are unreleased main. No runtime dependencies, secrets, private
producer artifacts, published package or release tags were changed. Existing
setuptools deprecations, live PR-comment delivery and source-archive installation
are not claimed resolved or newly qualified.
