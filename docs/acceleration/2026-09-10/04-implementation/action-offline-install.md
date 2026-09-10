# Make the composite Action execution path genuinely offline

## Problem

`pip install "$GITHUB_ACTION_PATH"` can invoke build isolation and attempt to obtain build requirements, even though the application itself has zero runtime dependencies. That weakens the offline/hermetic claim and creates avoidable supply-chain/network exposure.

## Preferred Action path

Run the checked-out source directly without installation:

```yaml
- name: Run gate
  id: gate
  shell: bash
  env:
    PYTHONPATH: ${{ github.action_path }}/src
    IN_DATASET: ${{ inputs.dataset }}
    # remaining inputs...
  run: |
    set +e
    python -m llm_release_gate gate "${args[@]}"
    code=$?
    echo "cli-exit=$code" >> "$GITHUB_OUTPUT"
    exit 0
```

This keeps the Marketplace Action path network-free after `actions/setup-python` has supplied Python. It also avoids an editable-install/worktree ambiguity.

## Alternative

Where installation is required, use:

```bash
python -m pip install --no-deps --no-build-isolation "$GITHUB_ACTION_PATH"
```

This assumes compatible build tooling is already present and still performs a package build. Test it in a network-disabled environment before describing it as offline.

## Boundaries

- `actions/setup-python` itself is a separate external Action and may download Python; “offline” should mean the gate does not need model APIs, package indexes, or provider keys after runner/toolchain setup.
- Pin external Actions to reviewed full commit SHAs in workflows that require stronger supply-chain immutability.
- Keep user-controlled inputs in environment variables, not embedded in shell script expressions.

## Tests

- Action self-test with pip index/network disabled;
- source path containing spaces;
- green and deliberate-red examples;
- outputs and job summary on gate exit 0/1/2;
- missing PR write permission leaves verdict intact;
- supported Python matrix and self-hosted runner requirement.
