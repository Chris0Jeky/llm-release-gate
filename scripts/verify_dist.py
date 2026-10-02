"""Verify release archives and optionally smoke a wheel in a fresh offline venv."""

from __future__ import annotations

import argparse
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
