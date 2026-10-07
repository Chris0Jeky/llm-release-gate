"""Exercise synthetic bound replay and stale-evidence refusal without API keys.

Only known demo artifacts in --out are replaced, as with the other make demos.
Temporary plans use fresh directories; the plan CLI itself never overwrites.
"""

from __future__ import annotations

import argparse
from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory

from llm_release_gate.cli import main as cli_main


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples/request-bound-replay"


def exercise(out: Path) -> None:
    with TemporaryDirectory(prefix="lrg-binding-") as temporary:
        work = Path(temporary)
        plan_argv = ["plan", "--dataset", str(EXAMPLE / "dataset.json"),
                     "--config", str(EXAMPLE / "candidate.json"), "--max-input-bytes", "1048576"]
        for target in (work / "plan-a", work / "plan-b"):
            if cli_main(plan_argv + ["--out", str(target)]) != 0:
                raise RuntimeError("synthetic request planning failed")
        if (work / "plan-a/plan.json").read_bytes() != (work / "plan-b/plan.json").read_bytes():
            raise RuntimeError("request plan changed across output directories")

        gate_argv = ["gate", "--require-request-binding", "--max-input-bytes", "1048576"]
        for key in ("dataset", "baseline", "candidate", "scorers", "thresholds"):
            gate_argv += ["--" + key, str(EXAMPLE / (key + ".json"))]
        valid_exit = cli_main(gate_argv + ["--out", str(work / "valid")])
        if valid_exit != 0:
            raise RuntimeError(f"valid synthetic bound replay returned {valid_exit}, expected 0")

        config = json.loads((EXAMPLE / "candidate.json").read_text(encoding="utf-8"))
        config["prompt"]["template"] += "\nA new instruction not used to construct these fixtures."
        config["provider_options"]["fixtures"] = str(EXAMPLE / "fixtures/candidate.json")
        stale_path = work / "stale-config.json"
        stale_path.write_text(json.dumps(config), encoding="utf-8")
        stale_args = list(gate_argv)
        stale_args[stale_args.index("--candidate") + 1] = str(stale_path)
        error, output = io.StringIO(), io.StringIO()
        with redirect_stderr(error), redirect_stdout(output):
            stale_exit = cli_main(stale_args + ["--out", str(work / "stale")])
        if stale_exit != 2 or "request binding mismatch" not in error.getvalue():
            raise RuntimeError("stale synthetic evidence was not refused as a binding error")
        if (work / "stale").exists():
            raise RuntimeError("stale evidence produced output")

        # Publish only completed deterministic demo artifacts, not temporary manifests.
        out.mkdir(parents=True, exist_ok=True)
        for name in ("report.json", "report.md", "report.html"):
            shutil.copyfile(work / "valid" / name, out / name)
        shutil.copyfile(work / "plan-a/plan.json", out / "plan.json")
        receipt = {"synthetic": True, "valid_exit": valid_exit, "stale_exit": stale_exit,
                   "request_binding": "sha256-v1"}
        (out / "binding-check.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
        print("OK: synthetic bound replay passed; stale request evidence refused (exit 2)")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT / "out/request-bound-replay")
    exercise(parser.parse_args().out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
