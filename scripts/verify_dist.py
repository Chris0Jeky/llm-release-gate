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
    assert declared == [version], "project and package versions disagree"
    return version


def verify_archives(directory: Path) -> Path:
    version = project_version()
    project = tomllib.loads((PROJECT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    assert not project.get("dependencies"), "runtime dependencies declared"
    expected_dependencies = set()
    for extra, requirements in project.get("optional-dependencies", {}).items():
        for requirement in requirements:
            # This project's optional requirements are deliberately simple. Require
            # an explicit verifier update if conditional extras are introduced.
            assert ";" not in requirement, "conditional optional dependencies need explicit verification"
            expected_dependencies.add(f'{requirement};extra=="{extra}"')
    wheel = directory / f"llm_release_gate-{version}-py3-none-any.whl"
    sdists = list(directory.glob(f"*{version}.tar.gz"))
    assert len(sdists) == 1, "expected exactly one source archive"
    sdist = sdists[0]
    sdist_root = sdist.name.removesuffix(".tar.gz")
    with tarfile.open(sdist) as archive:
        for notice in NOTICES:
            member = archive.extractfile(f"{sdist_root}/{notice}")
            assert member is not None, f"sdist missing {notice}"
            assert member.read() == (PROJECT / notice).read_bytes(), notice
    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
        metadata = email.parser.BytesParser().parsebytes(
            archive.read(f"llm_release_gate-{version}.dist-info/METADATA")
        )
        assert metadata["Version"] == version
        assert metadata["License"] == "GPL-3.0-only"
        assert set(metadata.get_all("License-File", [])) == set(NOTICES)
        dependencies = {
            "".join(requirement.split()).replace("'", '"')
            for requirement in metadata.get_all("Requires-Dist", [])
        }
        assert dependencies == expected_dependencies, "archive dependencies differ from declared optional dependencies"
        for notice in NOTICES:
            matches = [name for name in names if name.endswith("/" + notice)]
            assert len(matches) == 1, f"wheel missing or duplicating {notice}"
            assert archive.read(matches[0]) == (PROJECT / notice).read_bytes(), notice
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
    assert not Path(plan_config["provider_options"]["fixtures"]).exists()
    plan_path = write_config("plan-config.json", plan_config)
    plan_out = temporary / "request-plan"
    plan_args = ["-m", "llm_release_gate", "plan", "--dataset", str(example / "dataset.json"),
                 "--config", str(plan_path), "--out", str(plan_out)]
    run(*plan_args)
    plan_bytes = (plan_out / "plan.json").read_bytes()
    plan = json.loads(plan_bytes)
    assert plan["schema_version"] == "lrg-request-plan/1"
    actual = {item["item_id"]: item["request_sha256"] for item in plan["requests"]}
    expected = {key: entry["request_sha256"]
                for key, entry in fixture["responses"][config["model"]].items()}
    assert len(plan["requests"]) == len(expected) and actual == expected, "plan request identities differ"
    refusal = run(*plan_args, expected=2)
    assert "plan output could not be created" in refusal.stderr
    assert (plan_out / "plan.json").read_bytes() == plan_bytes, "plan receipt was overwritten"

    args = ["-m", "llm_release_gate", "gate", "--require-request-binding"]
    for key in ("dataset", "baseline", "candidate", "scorers", "thresholds"):
        args.extend(("--" + key, str(example / (key + ".json"))))
    valid_out = temporary / "bound-gate"
    run(*args, "--out", str(valid_out), "--max-input-bytes", "1048576")
    report = json.loads((valid_out / "report.json").read_text(encoding="utf-8"))
    assert report["gate"]["verdict"] == "pass"
    for role in ("baseline", "candidate"):
        assert report["runs"][role]["provider"]["request_binding"] == "sha256-v1"
    assert report["metrics"]["cost.total_usd"]["candidate"]["available"] is False

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
        assert message in refusal.stderr and "Traceback" not in refusal.stderr, case
        assert not invalid_out.exists(), f"{case} emitted output"

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
    assert json.loads(diagnostics)["run"]["n_errors"] == 1
    refusal = run(*diagnostic_args, "--fail-on-errors", expected=2)
    assert "--fail-on-errors" in refusal.stderr and "Traceback" not in refusal.stderr
    assert (diagnostic_out / "run.json").read_bytes() == diagnostics
    print("Installed wheel plan/non-overwrite/bound/stale/downgrade/byte-limit/diagnostic: PASS")


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
            assert result.returncode == expected, (args, result.returncode, result.stdout, result.stderr)
            return result

        run("-m", "pip", "install", "--no-index", "--no-deps", str(wheel.resolve()))
        assert run("-m", "llm_release_gate", "--version").stdout.strip().endswith(version)
        installed = json.loads(run("-c", "import json,llm_release_gate,importlib.metadata;print(json.dumps([llm_release_gate.__file__,llm_release_gate.__version__,importlib.metadata.version('llm-release-gate')]))").stdout)
        assert Path(installed[0]).resolve().is_relative_to(environment.resolve())
        assert installed[1:] == [version, version]
        entrypoint = executable_dir / ("llm-release-gate.exe" if os.name == "nt" else "llm-release-gate")
        result = subprocess.run([str(entrypoint), "--version"], cwd=temporary, env=env, capture_output=True, text=True, timeout=60)
        assert result.returncode == 0 and result.stdout.strip().endswith(version)
        hashed = run("-m", "llm_release_gate", "hash", str(PROJECT / "examples/pricing.json"))
        assert "sha256:" in hashed.stdout
        for scenario, expected in (("rag-support-bot", 0), ("assistant-cheap-regression", 1)):
            example = PROJECT / "examples" / scenario
            args = ["-m", "llm_release_gate", "gate"]
            for key in ("dataset", "baseline", "candidate", "scorers", "thresholds"):
                args.extend(("--" + key, str(example / (key + ".json"))))
            args.extend(("--pricing", str(PROJECT / "examples/pricing.json"), "--out", str(temporary / scenario)))
            run(*args, expected=expected)
            report = json.loads((temporary / scenario / "report.json").read_text(encoding="utf-8"))
            assert report["gate"]["verdict"] == ("pass" if expected == 0 else "fail")
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
