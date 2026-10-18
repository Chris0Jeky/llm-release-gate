"""Verify release archives and optionally smoke a wheel in a fresh offline venv."""

from __future__ import annotations

import argparse
from collections.abc import Callable
import ast
import email.parser
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile
import tomllib
import venv
import zipfile


PROJECT = Path(__file__).resolve().parents[1]
NOTICES = ("LICENSE", "RELICENSING.md", "LICENSES/MIT.txt")


def project_version() -> str:
    version = tomllib.loads((PROJECT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
    source = ast.parse((PROJECT / "src/llm_release_gate/__init__.py").read_text(encoding="utf-8"))
    declared = [ast.literal_eval(node.value) for node in source.body if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == "__version__" for target in node.targets)]
    if declared != [version]:
        raise SystemExit("project and package versions disagree")
    return version


def verify_archives(directory: Path) -> Path:
    version = project_version()
    project = tomllib.loads((PROJECT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    if project.get("dependencies"):
        raise SystemExit("runtime dependencies declared")
    expected_dependencies = set()
    for extra, requirements in project.get("optional-dependencies", {}).items():
        for requirement in requirements:
            # This project's optional requirements are deliberately simple. Require
            # an explicit verifier update if conditional extras are introduced.
            if ';' in requirement:
                raise SystemExit("conditional optional dependencies need explicit verification")
            expected_dependencies.add(f'{requirement};extra=="{extra}"')
    wheel = directory / f"llm_release_gate-{version}-py3-none-any.whl"
    sdists = list(directory.glob(f"*{version}.tar.gz"))
    if len(sdists) != 1:
        raise SystemExit("expected exactly one source archive")
    sdist = sdists[0]
    sdist_root = sdist.name.removesuffix(".tar.gz")
    with tarfile.open(sdist) as archive:
        for notice in NOTICES:
            member = archive.extractfile(f"{sdist_root}/{notice}")
            if member is None:
                raise SystemExit(f"sdist missing {notice}")
            if member.read() != (PROJECT / notice).read_bytes():
                raise SystemExit(f"archive notice bytes differ: {notice}")
    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
        metadata = email.parser.BytesParser().parsebytes(
            archive.read(f"llm_release_gate-{version}.dist-info/METADATA")
        )
        if metadata['Version'] != version:
            raise SystemExit('wheel version differs from project version')
        if metadata['License'] != 'GPL-3.0-only':
            raise SystemExit('wheel license must be GPL-3.0-only')
        if set(metadata.get_all('License-File', [])) != set(NOTICES):
            raise SystemExit('wheel License-File metadata differs from required notices')
        dependencies = {
            "".join(requirement.split()).replace("'", '"')
            for requirement in metadata.get_all("Requires-Dist", [])
        }
        if dependencies != expected_dependencies:
            raise SystemExit("archive dependencies differ from declared optional dependencies")
        for notice in NOTICES:
            matches = [name for name in names if name.endswith("/" + notice)]
            if len(matches) != 1:
                raise SystemExit(f"wheel missing or duplicating {notice}")
            if archive.read(matches[0]) != (PROJECT / notice).read_bytes():
                raise SystemExit(f"archive notice bytes differ: {notice}")
    for artifact in (sdist, wheel):
        print(f"sha256 {hashlib.sha256(artifact.read_bytes()).hexdigest()} {artifact.name}")
    print("Archive licence bytes, metadata and zero runtime dependencies: PASS")
    return wheel


def smoke_replay_features(
    run: Callable[..., subprocess.CompletedProcess[str]], temporary: Path,
) -> None:
    """Qualify additive CLI features through the caller's isolated wheel runner.

    The fixture pair is explicitly synthetic. No live producer is called and no
    historical response is relabeled. Source files supply inputs only; all CLI
    execution uses the already installed wheel through ``run``.
    """
    example = PROJECT / "examples/request-bound-replay"
    config = json.loads((example / "candidate.json").read_text(encoding="utf-8"))
    fixture_path = example / "fixtures/candidate.json"
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))

    def write_config(name: str, value: dict) -> Path:
        path = temporary / name
        path.write_text(json.dumps(value), encoding="utf-8")
        return path

    # Planning must work before evidence exists and refuse to replace its receipt.
    plan_config = json.loads(json.dumps(config))
    plan_config["provider_options"]["fixtures"] = str(temporary / "not-collected.json")
    if Path(plan_config["provider_options"]["fixtures"]).exists():
        raise SystemExit('release verification failed: not Path(plan_config["provider_options"]["fixtures"]).exists()')
    plan_path = write_config("plan-config.json", plan_config)
    plan_out = temporary / "request-plan"
    plan_args = ["-m", "llm_release_gate", "plan", "--dataset", str(example / "dataset.json"),
                 "--config", str(plan_path), "--out", str(plan_out)]
    run(*plan_args)
    plan_bytes = (plan_out / "plan.json").read_bytes()
    plan = json.loads(plan_bytes)
    if plan['schema_version'] != 'lrg-request-plan/1':
        raise SystemExit('release verification failed: plan["schema_version"] == "lrg-request-plan/1"')
    actual = {item["item_id"]: item["request_sha256"] for item in plan["requests"]}
    expected = {key: entry["request_sha256"]
                for key, entry in fixture["responses"][config["model"]].items()}
    if not (len(plan["requests"]) == len(expected) and actual == expected):
        raise SystemExit("plan request identities differ")
    refusal = run(*plan_args, expected=2)
    if 'plan output could not be created' not in refusal.stderr:
        raise SystemExit('release verification failed: "plan output could not be created" in refusal.stderr')
    if (plan_out / 'plan.json').read_bytes() != plan_bytes:
        raise SystemExit("plan receipt was overwritten")

    args = ["-m", "llm_release_gate", "gate", "--require-request-binding"]
    for key in ("dataset", "baseline", "candidate", "scorers", "thresholds"):
        args.extend(("--" + key, str(example / (key + ".json"))))
    valid_out = temporary / "bound-gate"
    run(*args, "--out", str(valid_out), "--max-input-bytes", "1048576")
    report = json.loads((valid_out / "report.json").read_text(encoding="utf-8"))
    if report['gate']['verdict'] != 'pass':
        raise SystemExit('release verification failed: report["gate"]["verdict"] == "pass"')
    for role in ("baseline", "candidate"):
        if report['runs'][role]['provider']['request_binding'] != 'sha256-v1':
            raise SystemExit('release verification failed: report["runs"][role]["provider"]["request_binding"] == "sha256-v1"')
    if report['metrics']['cost.total_usd']['candidate']['available'] is not False:
        raise SystemExit('release verification failed: report["metrics"]["cost.total_usd"]["candidate"]["available"] is False')

    manifest = json.loads((valid_out / "manifest.json").read_text(encoding="utf-8"))
    verify_args = ["-m", "llm_release_gate", "verify", "--bundle", str(valid_out),
                   "--expected-result-hash", report["result_hash"],
                   "--expected-bundle-hash", manifest["bundle_integrity"]["bundle_hash"],
                   "--require-pass", "--json"]
    verification = json.loads(run(*verify_args).stdout)
    if not (verification["integrity"] == "verified" and verification["gate_verdict"] == "pass"):
        raise SystemExit('release verification failed: verification["integrity"] == "verified" and verification["gate_verdict"] == "pass"')
    if verification['external_pins'] != {'result_hash': True, 'bundle_hash': True}:
        raise SystemExit('release verification failed: verification["external_pins"] == {"result_hash": True, "bundle_hash": True}')
    if verification['authenticity_verified'] is not False:
        raise SystemExit('release verification failed: verification["authenticity_verified"] is False')
    consumer_policy = example / "consumer-policy.json"
    policy_hash = "sha256:" + hashlib.sha256(consumer_policy.read_bytes()).hexdigest()
    audit_args = ["-m", "llm_release_gate", "audit", "--bundle", str(valid_out),
                  "--thresholds", str(consumer_policy), "--expected-policy-hash", policy_hash,
                  "--expected-result-hash", report["result_hash"],
                  "--expected-bundle-hash", manifest["bundle_integrity"]["bundle_hash"], "--json"]
    audited = json.loads(run(*audit_args, expected=1).stdout)
    if not (audited["recorded_gate_verdict"] == "pass" and audited["policy_verdict"] == "fail"):
        raise SystemExit('release verification failed: audited["recorded_gate_verdict"] == "pass" and audited["policy_verdict"] == "fail"')
    if audited['external_pins'] != {'result_hash': True, 'bundle_hash': True, 'policy_hash': True}:
        raise SystemExit('release verification failed: audited["external_pins"] == {"result_hash": True, "bundle_hash": True, "policy_hash": True}')
    if not (audited["scores_recomputed"] is False and audited["authenticity_verified"] is False):
        raise SystemExit('release verification failed: audited["scores_recomputed"] is False and audited["authenticity_verified"] is False')
    cost_rule = next(rule for rule in audited["rules"] if rule["metric"] == "cost.total_usd")
    if cost_rule['checks'][0]['status'] != 'unavailable':
        raise SystemExit('release verification failed: cost_rule["checks"][0]["status"] == "unavailable"')
    bad_pin_args = list(audit_args)
    bad_pin_args[bad_pin_args.index("--expected-policy-hash") + 1] = "sha256:" + "0" * 64
    refusal = run(*bad_pin_args, expected=2)
    if not ("expected policy hash" in refusal.stderr and "Traceback" not in refusal.stderr):
        raise SystemExit('release verification failed: "expected policy hash" in refusal.stderr and "Traceback" not in refusal.stderr')
    print("Installed wheel pinned consumer-policy audit and wrong-policy refusal: PASS")

    original_markdown = (valid_out / "report.md").read_bytes()
    (valid_out / "report.md").write_bytes(original_markdown + b"tampered")
    refusal = run(*verify_args, expected=2)
    if not ("digest or size mismatch" in refusal.stderr and "Traceback" not in refusal.stderr):
        raise SystemExit('release verification failed: "digest or size mismatch" in refusal.stderr and "Traceback" not in refusal.stderr')
    (valid_out / "report.md").write_bytes(original_markdown)

    for case, message in (("stale", "request binding mismatch"),
                          ("unbound", "requires fake provider request_binding"),
                          ("oversize", "exceeds max input size")):
        changed = json.loads(json.dumps(config))
        changed["provider_options"]["fixtures"] = str(fixture_path)
        if case == "stale":
            changed["prompt"]["template"] += "\nThis instruction was not used for these fixtures."
        elif case == "unbound":
            del changed["provider_options"]["request_binding"]
        invalid_args = list(args)
        invalid_args[invalid_args.index("--candidate") + 1] = str(write_config(case + ".json", changed))
        invalid_out = temporary / (case + "-output")
        if case == "oversize":
            invalid_args.extend(("--max-input-bytes", "1"))
        refusal = run(*invalid_args, "--out", str(invalid_out), expected=2)
        if not (message in refusal.stderr and "Traceback" not in refusal.stderr):
            raise SystemExit(case)
        if invalid_out.exists():
            raise SystemExit(f"{case} emitted output")

    # Preserve a correctly bound error entry: the diagnostic flag changes exit
    # status, not collection or the report payload. No cost/usage is invented.
    responses = fixture["responses"][config["model"]]
    first = next(iter(responses))
    responses[first] = {"request_sha256": responses[first]["request_sha256"],
                        "error": "synthetic installed-wheel probe"}
    failed_fixture = write_config("failed-fixture.json", fixture)
    config["provider_options"]["fixtures"] = str(failed_fixture)
    failed_config = write_config("failed-config.json", config)
    diagnostic_out = temporary / "diagnostic"
    diagnostic_args = ["-m", "llm_release_gate", "run", "--dataset", str(example / "dataset.json"),
                       "--config", str(failed_config), "--scorers", str(example / "scorers.json"),
                       "--out", str(diagnostic_out), "--require-request-binding"]
    run(*diagnostic_args)
    diagnostics = (diagnostic_out / "run.json").read_bytes()
    if json.loads(diagnostics)['run']['n_errors'] != 1:
        raise SystemExit('release verification failed: json.loads(diagnostics)["run"]["n_errors"] == 1')
    refusal = run(*diagnostic_args, "--fail-on-errors", expected=2)
    if not ("--fail-on-errors" in refusal.stderr and "Traceback" not in refusal.stderr):
        raise SystemExit('release verification failed: "--fail-on-errors" in refusal.stderr and "Traceback" not in refusal.stderr')
    if (diagnostic_out / 'run.json').read_bytes() != diagnostics:
        raise SystemExit('release verification failed: (diagnostic_out / "run.json").read_bytes() == diagnostics')
    print("Installed wheel plan/non-overwrite/bound/stale/downgrade/byte-limit/diagnostic/bundle-verification: PASS")


def smoke_wheel(wheel: Path) -> None:
    version = project_version()
    out = PROJECT / "out"
    out.mkdir(exist_ok=True)
    env = dict(os.environ)
    for key in ("PYTHONPATH", "PYTHONHOME", "GITHUB_OUTPUT", "GITHUB_STEP_SUMMARY"):
        env.pop(key, None)
    with tempfile.TemporaryDirectory(prefix="release-smoke-", dir=out) as temporary:
        temporary = Path(temporary)
        environment = temporary / "venv"
        venv.EnvBuilder(with_pip=True).create(environment)
        executable_dir = environment / ("Scripts" if os.name == "nt" else "bin")
        python = executable_dir / ("python.exe" if os.name == "nt" else "python")

        def run(*args: str, expected: int = 0) -> subprocess.CompletedProcess[str]:
            result = subprocess.run(
                [str(python), "-I", *args], cwd=temporary, env=env,
                capture_output=True, text=True, timeout=60,
            )
            if result.returncode != expected:
                raise SystemExit((args, result.returncode, result.stdout, result.stderr))
            return result

        run("-m", "pip", "install", "--no-index", "--no-deps", str(wheel.resolve()))
        if not (run("-m", "llm_release_gate", "--version").stdout.strip().endswith(version)):
            raise SystemExit('release verification failed: run("-m", "llm_release_gate", "--version").stdout.strip().endswith(version)')
        installed = json.loads(run("-c", "import json,llm_release_gate,importlib.metadata;print(json.dumps([llm_release_gate.__file__,llm_release_gate.__version__,importlib.metadata.version('llm-release-gate')]))").stdout)
        if not (Path(installed[0]).resolve().is_relative_to(environment.resolve())):
            raise SystemExit('release verification failed: Path(installed[0]).resolve().is_relative_to(environment.resolve())')
        if installed[1:] != [version, version]:
            raise SystemExit('release verification failed: installed[1:] == [version, version]')
        entrypoint = executable_dir / ("llm-release-gate.exe" if os.name == "nt" else "llm-release-gate")
        result = subprocess.run([str(entrypoint), "--version"], cwd=temporary, env=env, capture_output=True, text=True, timeout=60)
        if not (result.returncode == 0 and result.stdout.strip().endswith(version)):
            raise SystemExit('release verification failed: result.returncode == 0 and result.stdout.strip().endswith(version)')
        hashed = run("-m", "llm_release_gate", "hash", str(PROJECT / "examples/pricing.json"))
        if 'sha256:' not in hashed.stdout:
            raise SystemExit('release verification failed: "sha256:" in hashed.stdout')
        for scenario, expected in (("rag-support-bot", 0), ("assistant-cheap-regression", 1)):
            example = PROJECT / "examples" / scenario
            args = ["-m", "llm_release_gate", "gate"]
            for key in ("dataset", "baseline", "candidate", "scorers", "thresholds"):
                args.extend(("--" + key, str(example / (key + ".json"))))
            args.extend(("--pricing", str(PROJECT / "examples/pricing.json"), "--out", str(temporary / scenario)))
            run(*args, expected=expected)
            report = json.loads((temporary / scenario / "report.json").read_text(encoding="utf-8"))
            if report['gate']['verdict'] != ('pass' if expected == 0 else 'fail'):
                raise SystemExit('release verification failed: report["gate"]["verdict"] == ("pass" if expected == 0 else "fail")')
        smoke_replay_features(run, temporary)
        print(f"Fresh offline wheel install/import/entrypoint/version/hash/green/red: PASS ({version})")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()
    wheel = verify_archives(args.directory.resolve())
    if args.smoke:
        smoke_wheel(wheel)


if __name__ == "__main__":
    main()
