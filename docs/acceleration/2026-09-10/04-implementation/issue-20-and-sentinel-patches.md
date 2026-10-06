# Reference patches: issue #20 and field-match sentinel

## Issue #20: Claude permissions

Current concerns:

- `Bash(gh :*)` matches nothing useful because the wildcard syntax is malformed.
- changing it mechanically to `Bash(gh:*)` would grant broad GitHub CLI mutation capability.
- `Bash(rg:*)` is not read-only because `rg --pre COMMAND` executes another program.
- repository notes that place `bypassPermissions` in project/local settings are stale for current Claude Code behaviour.

### Current repository repair

Remove both `Bash(rg:*)` and the malformed `Bash(gh :*)` from the committed
allow list. Do not replace either with broader access. Built-in `Read`, `Grep`
and `Glob` remain available; no GitHub CLI command family is auto-allowed by this
repair. Any future narrow `gh` allow rule needs its own runtime-matcher checks.

The 2026-10-03 owner decision recorded in `.agent-harness/tier.json` supersedes
this bundle's September baseline: keep no project `defaultMode`, preserving the
owner's user-scope permission mode. Do not add a project/local bypass recipe or
restore a project `acceptEdits` override. Existing deny entries are unchanged.

### Verification and limits

`tests/test_claude_permissions.py` validates JSON, removal of both rules, absence
of replacement `gh` rules, retained read tools/deny entries, and the current
owner-scope documentation. This is a static repository contract check, **not a runtime permission-matcher proof**.

No Claude permission matcher was executed for this repair. User-scope settings,
hooks, bypass mode, and other existing shell permissions remain outside this
check. Removing these entries is not a claim that every possible command is
sandboxed or that owner-selected bypass mode is disabled. Test actual matching
before adding new shell allows; never infer it from a prefix-only imitation.

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
