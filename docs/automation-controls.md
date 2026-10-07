# Automation controls

These additions are on main and are not yet included in a new tagged release.
They address the remaining operational concerns in issue #30 without changing
the defaults or the explicit-error-rule override policy.

## Bound input reads

Append `--max-input-bytes 1048576` to `gate` or `run` to admit at most one MiB
of **raw bytes per JSON source**. All five gate inputs, optional pricing, and
both referenced fixture files use the same scoped limit. UTF-8 multibyte
characters and physical CRLF bytes count before decoding and normalization.
The exact boundary is accepted; one byte over it is refused before JSON parsing.
An invalid flag or an oversized source yields exit 2. No partial source is parsed.

The check uses the existing nonblocking, regular-file-verified descriptor and
reads in chunks of at most 64 KiB, stopping after at most limit + 1 bytes.
It does not trust a prior path stat or allocate the full requested limit up front.
Symlinks to regular files retain the existing contract; special-file targets do
not become readable through a symlink. Later or nested invocations cannot inherit
a completed invocation's cap accidentally.

The same option in a workflow step using this Action is:

```yaml
with:
  # Supply the usual dataset/baseline/candidate/scorers/thresholds inputs too.
  max-input-bytes: "1048576"
```

The value travels through an environment variable and a quoted Bash array
argument, not shell-script interpolation. Empty means unlimited; zero is invalid.
The hosted self-test checks both acceptance and refusal through `action.yml`.

For direct library use:

```python
from llm_release_gate.loading import input_byte_limit, load_dataset

with input_byte_limit(1048576):
    dataset = load_dataset("dataset.json")
    # Other loaders and synchronous run_config calls here share the cap.
```

The scope uses ContextVar set/reset (compatible with Python 3.11), not a mutable
process-global knob. An out-of-tree provider that reads files without the shared
loader, or creates fresh threads, is outside this guarantee and must implement
its own bound. The current built-in replay provider uses the shared loader.

**Limits:** this is not a process sandbox, a total-run byte budget, a time limit,
or a bound on decoded strings, Python object overhead, JSON nesting or CPU.
Choose a suitable cap and use OS/container resource limits for untrusted jobs.
No default cap is introduced. On successful bounded gate runs, the manifest
records `execution_options.max_input_bytes`; report bytes and hashes remain
unchanged for otherwise identical accepted inputs.

## Fail diagnostic automation explicitly

Append `--fail-on-errors` to an existing `run` invocation. The command finishes
collecting per-item diagnostics, writes the same `run.json`, and then exits 2
when `run.n_errors > 0`. Partial and total failures are both covered. Successful
runs exit 0. Configuration errors still abort with exit 2 as before.

Without this flag, `run` retains its existing diagnostic exit-0 behavior. Exit 1
remains the gate's policy-regression result, not a diagnostic provider status.
The flag does not change `gate`, thresholds, implicit errors.error_rate handling,
or the ability of an explicit error rule to override the default implicit rule.
A parse/scoring result considered `ok` by the runner is not reclassified by the
flag: use actual quality/schema thresholds to decide acceptability.

## Output reuse

Input refusal emits no new report or verdict. It does not delete old reports in
a reused output directory. Always select a fresh per-invocation output directory
and honor the command exit code; existence of an old report is not a new verdict.
