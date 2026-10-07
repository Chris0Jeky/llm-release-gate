# Evidence integrity progress

This checkpoint adds safe publication and offline consumption to the previously
merged request-binding path. Changes are unreleased main, not a release or tag move.

| Merged slice | Qualified head | Merge | Hosted PR CI | Full suite |
|---|---|---|---|---:|
| [#85 output safety](https://github.com/Chris0Jeky/llm-release-gate/pull/85) | `3e0ddd40785a465d3cf093637ecb0352c7a8bdc1` | `ab8b09cf347c362698d9b40a5b486fc0e9279bfa` | [37562637819](https://github.com/Chris0Jeky/llm-release-gate/actions/runs/37562637819) | 536 |
| [#86 bundle verification](https://github.com/Chris0Jeky/llm-release-gate/pull/86) | `2bfe618452780b032c8cb801e6fe394835a27de6` | `730d778006a726c4dc302f57a09fe271c15f2c7d` | [37564246084](https://github.com/Chris0Jeky/llm-release-gate/actions/runs/37564246084) | 601 |

Both slices passed Python 3.11/3.13, package/fresh-wheel acceptance, Action scenarios
and the 14-file deterministic report/plan comparison before SHA-guarded merges.
Reviews were documented self-reviews, not independent approvals. New regression
cases were observed failing before implementation. The starting source tree was
reconstructed from supplied archives/patches and matched live main exactly; no
raw GitHub download through the generic shell was used for repository work.

## Reproduced and repaired

Output paths could overwrite loaded inputs/fixtures or follow final symlinks;
a late rendering failure could leave mixed old/new evidence. #85 stages everything
first, validates source/destination identities, serializes cooperating publishers,
and restores prior artifacts after caught write failures. Incomplete rollback
retains backups, a recovery map and the lock. It does not claim a power-loss
transaction or protection against hostile writers ignoring the lock.

#86 adds a versioned receipt and read-only `verify` command. It checks raw report
bytes, canonical manifest content, matching headers, optional externally trusted
pins, strict JSON and filesystem boundaries. It never follows stored source paths,
reruns providers, recomputes policy, or calls internally consistent evidence a new
passing gate. The Action and installed-wheel acceptance exercise it directly.
An unpinned full rewrite can still be self-consistent; that limitation is tested.

## Command transport follow-up

The next slice repairs separately reproduced workflow output injection and
command-file alias destruction. The old enforcement script also evaluated an
injected status as shell code and allowed shell exit-code wrapping. The repair
uses literal multiline framing with collision-checked delimiters, descriptor and
alias checks for command files, and an environment-fed status case statement.
The ordinary wrapper emits numeric statuses; no production exploit is claimed.

The first transport regression run had 26 failures and seven existing-behavior
passes. A later hosted-wiring assertion also failed before its implementation.
The integrated local `make ci` passes **637 tests**, all four demos and offline
bundle checks. The transport PR's own current-head CI, including real runner
multiline-output parsing, must qualify it; earlier PR receipts do not substitute
for that evidence. Read the final PR discussion for its merge and main-push receipt.

## Boundaries and resume

[Output safety](output-safety.md), [bundle verification](bundle-verification.md),
and [GitHub command safety](github-command-safety.md) document contracts and limits.
Report schema/default replay/default threshold policies and all four deterministic
example result hashes are unchanged. Bundle hashes include volatile invocation
metadata and are not expected to match across independent runs.

No real provider, credential, runtime dependency, private producer artifact,
release tag or published package was changed. Live PR-comment delivery, source
archive installation and hostile-filesystem atomicity are not claimed verified.
Existing setuptools metadata deprecation warnings remain outside these fixes.

#24 still requires approved producer artifacts and schema qualification before
an HQ evidence consumer. #35 retains the first-real-provider latency-boundary
trigger. Neither is completed by this work. Source-private artifacts must not
be copied into this public repository to bypass those conditions.

Refresh main, open PRs, review threads and exact-head CI. Reconcile the command
transport follow-up first; do not redo #85/#86 or the earlier #78-#84 changes.
A release is a separate qualification/publication decision; do not move `v0`
merely because main has advanced.
