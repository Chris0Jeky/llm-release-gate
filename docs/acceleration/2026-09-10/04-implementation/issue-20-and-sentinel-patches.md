# Reference patches: issue #20 and field-match sentinel

## Issue #20: Claude permissions

Current concerns:

- `Bash(gh :*)` matches nothing useful because the wildcard syntax is malformed.
- changing it mechanically to `Bash(gh:*)` would grant broad GitHub CLI mutation capability.
- `Bash(rg:*)` is not read-only because `rg --pre COMMAND` executes another program.
- repository notes that place `bypassPermissions` in project/local settings are stale for current Claude Code behaviour.

### Bounded patch shape

Remove the `rg` rule. Replace broad `gh` access with the smallest read-only commands actually needed by the repository harness, for example exact families for status/list/view operations after testing the runtime matcher. Do not auto-allow `gh api`, release mutations, issue edits, workflow dispatch, secret operations, or arbitrary extension commands.

Update `.agent-harness/tier.json`, `CLAUDE.md`, `AGENTS.md`, or related estate notes only where they repeat the obsolete local bypass recipe. Keep `defaultMode: acceptEdits` as the committed baseline.

### Verification

- validate JSON;
- exercise every intended allow and representative near-miss/deny command through the actual permission matcher;
- prove `rg --pre`, broad `gh api`, release mutation, force push, and destructive shell commands are not auto-approved;
- run repository docs/config checks and close #20 with measured evidence.

## Field-match missing sentinel

Current code uses the literal string `"<missing>"` as a fallback. A legitimate expected value equal to that string can therefore pass when the field is absent.

```python
_MISSING = object()

for key, want in expected_fields.items():
    got = output.json_obj.get(key, _MISSING)
    if got is _MISSING:
        mismatches.append(f"{key}: missing")
    elif not json_equal(got, want):
        mismatches.append(f"{key}: expected {want!r}, got {got!r}")
```

### Tests

- absent field with expected `"<missing>"` fails;
- present field with literal `"<missing>"` passes;
- absent field detail says `missing`, not a fabricated received value;
- nested bool/int strict equality remains intact;
- output with non-object JSON follows the existing parse/schema failure path.
