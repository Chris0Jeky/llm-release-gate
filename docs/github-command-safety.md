# GitHub command-file safety

This repair is on unreleased main. It changes transport and refusal behavior,
not report content, threshold policy or the normal CLI 0/1/2 contract.

## Literal output values

The CLI uses GitHub's command-file protocol, not stdout workflow commands.
Single-line values retain `name=value` form. Multiline values use the documented
heredoc form with a delimiter chosen after inspecting every line in the value;
it cannot collide with an existing payload line. Newlines inside a path therefore
remain part of that output value instead of creating forged `verdict`, hash or
path outputs. Output names must be simple identifiers; NUL and non-UTF-8 values
are rejected before appending any output commands.

This protects the file-command boundary. Consumers must still pass values through
environment variables or another data interface, never interpolate arbitrary
outputs into shell source. It does not make an untrusted path safe to execute.

## Protect command-file destinations

Before publishing a gate bundle, both configured command-file destinations are
checked alongside the report destinations. `GITHUB_OUTPUT` and
`GITHUB_STEP_SUMMARY` may not alias loaded inputs, transitive fixtures, report
artifacts, each other, or the publication lock filename. Final symlinks,
directories and special files are refused. Appending rechecks opened descriptor
identity and uses no-follow/nonblocking flags where supported. New command files
use private mode 0600 where supported; existing runner-owned files are appended.

These checks prevent ordinary misconfiguration from corrupting evidence. They
are not a hostile-filesystem sandbox. Command-file appends are not part of the
report bundle's rollback transaction, and a later append failure still returns
exit 2 even if the bundle was already published. Honor the command status.

## Enforce only recognized status values

The Action passes the CLI status through `GATE_EXIT_CODE`, not an expression
embedded in Bash source. A literal `0` passes, `1` fails for policy regression,
and every other value returns 2. This avoids shell evaluation and shell exit-code
wrapping (for example, `exit 256` becoming success). The ordinary wrapper produces
numeric CLI statuses; the adversarial tests do not claim an observed production
exploit of that wrapper. They prove the enforcement boundary fails closed even
with malformed or injected upstream data.

`tests/test_github_command_safety.py` exercises the actual enforcement Bash,
command-file parsing, aliases and non-UTF-8 refusal. Hosted CI additionally sends
an adversarial multiline value through the real runner parser and checks that
its embedded assignment text cannot change the genuine verdict or create another
output. It retains the Action's actual pinned-bundle verification.

References: [GitHub workflow commands](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-commands)
and [GitHub script injection guidance](https://docs.github.com/en/actions/concepts/security/script-injections).
