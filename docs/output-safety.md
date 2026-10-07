# Evidence output safety

The gate renders its complete JSON/Markdown/HTML report and manifest before
publishing any artifact. Diagnostic `run` uses the same publisher for `run.json`.
The `plan` command retains its separate exclusive, non-overwriting output.

## Refusals before publication

Each CLI invocation captures the path and opened-file identity of every JSON
source it reads, including transitive replay fixtures. Report destinations may
not replace those inputs, either by path or through an existing hardlink.
Destinations must be absent or regular files; final symlinks (including dangling
ones), directories and special files are refused. Two destinations that alias
each other are refused. These checks apply to diagnostic output too.

Parent directories may be symlinks, for compatibility with ordinary linked
workspaces. This is protection against accidental input destruction and final
output-link traversal, not a sandbox against a hostile directory owner.
Only the declared output filenames are changed; unrelated files are retained.

## Staging and failure recovery

A `.llm-release-gate.lock` file serializes cooperating publishers in an output
directory. The publisher stages complete UTF-8 files and backups of existing
artifacts in a private `.lrg-stage-*` directory. It checks destination identities
again, then replaces each destination atomically, with the manifest last.
Existing permission bits are retained. New output files use private mode 0600
where the operating system supports POSIX permission bits.

A caught replacement failure restores the already-replaced files or removes newly
created ones. If restoration also fails, the staging directory, original backups,
`recovery.json` destination map, and lock are retained. The command returns exit 2
and identifies the recovery location. Further CLI writers refuse the lock.
Do not automatically delete a lock: first establish that its writer has stopped,
inspect the recovery map, and restore the intended previous artifacts. Backups
may contain sensitive evidence and should receive the same handling as reports.

Per-file replacement is atomic; the complete multi-file bundle is **not** a
power-loss or process-crash transaction. A terminated process can leave a lock,
staging files or a mixed-generation bundle. External writers and readers that
ignore the lock are not coordinated by this mechanism. File existence alone is
never proof of a successful invocation; consumers must honor exit codes and
verify evidence identity. Prefer a fresh output directory for each invocation.

Input rejection does not delete artifacts from a prior run. Rendering failures
leave prior artifacts untouched; staging failures publish nothing; simulated
replacement failures and incomplete rollback have explicit regression coverage
in `tests/test_output_safety.py`.

New gate manifests include a [bundle integrity receipt](bundle-verification.md).
A copied, unlocked bundle can be checked with `verify --bundle DIRECTORY`; supply
an expected bundle hash from a trusted channel to detect a complete rewrite.
Verification never removes a publication lock or performs recovery automatically.
