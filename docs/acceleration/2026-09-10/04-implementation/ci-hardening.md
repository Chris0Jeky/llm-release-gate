# CI, package, and dependency hardening

## Objectives

Prove the distributed forms that users actually consume and reduce movable third-party workflow dependencies.

## Recommended lanes

1. **Unit/integration matrix:** supported Python versions on Ubuntu; add one Windows smoke job for CLI/path/newline behaviour.
2. **Examples:** both green examples pass and deliberate regression exits exactly 1.
3. **Composite Action self-test:** exercise `uses: ./` and outputs on green/red cases.
4. **Distribution:** build sdist and wheel, inspect licence files, install wheel in a clean environment, run `--version`, `hash`, one green gate, and the deliberate-red gate.
5. **Static workflow checks:** YAML parse plus Action/shell validation. Introduce external linters only after deciding how they are pinned and obtained.
6. **Bundle smoke:** parse decision/issue/risk JSON, compile `unbundle.py`, validate relative file references, and dry-run it against the example decision export in a temporary Git checkout.

## Least privilege

Declare workflow permissions at top level and elevate only the job/step that posts PR comments:

```yaml
permissions:
  contents: read
```

Document that `pull-requests: write` is optional and only enables comments. Keep the gate enforcement independent from comment success.

## Action pinning

For high-assurance workflows, pin `actions/checkout`, `actions/setup-python`, and `actions/upload-artifact` to reviewed full commit SHAs with a comment naming the release. Do not copy stale example SHAs from this document; resolve and review current upstream commits when implementing.

## Dependabot

Add a GitHub Actions ecosystem update entry with a modest cadence and grouped updates. Review runtime-major changes separately because GitHub-hosted and self-hosted runner requirements can change.

## Release proof

A release tag must point at an exact commit where all required checks are green. Re-run/verify tag peeling, release metadata, Marketplace resolution, version output, licence contents, and floating-tag movement after publication.
