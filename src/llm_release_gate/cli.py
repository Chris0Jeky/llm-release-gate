"""Command-line interface.

Exit codes (the CI contract, tested in tests/test_cli.py):
  0 — gate evaluated, no fail-level threshold breached
  1 — gate evaluated, at least one fail-level threshold breached
  2 — the gate could not run (bad config, missing file, internal error)

GitHub integration is env-driven and needs no flags: when GITHUB_STEP_SUMMARY
is set the Markdown report is appended to the job summary; when GITHUB_OUTPUT
is set, verdict / report paths / result_hash are exported as step outputs.
Posting the PR comment is the Action's job (see action.yml), keeping the CLI
free of network calls and tokens.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import traceback

from . import TOOL_NAME, __version__
from .errors import GateConfigError
from .gate import build_report
from .hashing import file_sha256
from .loading import (
    load_dataset, load_pricing, load_run_config, load_scorer_config,
    load_thresholds, no_pricing, input_byte_limit, RunConfig,
)
from .manifest import build_manifest
from .reports.html import render_html
from .reports.markdown import render_markdown
from .runner import run_config
from .requests import BINDING_SCHEME
from .scorers import build_scorers

EXIT_PASS = 0
EXIT_GATE_FAIL = 1
EXIT_ERROR = 2


def _write(path: str, content: str) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(content)


def _emit_github_outputs(pairs: dict) -> None:
    output_path = os.environ.get("GITHUB_OUTPUT")
    if not output_path:
        return
    with open(output_path, "a", encoding="utf-8") as fh:
        for key, value in pairs.items():
            fh.write(f"{key}={value}\n")


def _emit_github_summary(markdown: str) -> None:
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not summary_path:
        return
    with open(summary_path, "a", encoding="utf-8") as fh:
        fh.write(markdown + "\n")


def _require_binding(config: RunConfig, required: bool) -> None:
    if required and (config.provider != "fake" or
                     config.provider_options.get("request_binding") != BINDING_SCHEME):
        raise GateConfigError("--require-request-binding requires fake provider "
                              "request_binding='sha256-v1' on every run config")


def _cmd_gate(args: argparse.Namespace) -> int:
    dataset = load_dataset(args.dataset)
    baseline_cfg = load_run_config(args.baseline, "baseline")
    candidate_cfg = load_run_config(args.candidate, "candidate")
    _require_binding(baseline_cfg, args.require_request_binding)
    _require_binding(candidate_cfg, args.require_request_binding)
    scorer_cfg = load_scorer_config(args.scorers)
    thresholds = load_thresholds(args.thresholds)
    pricing = load_pricing(args.pricing) if args.pricing else no_pricing()
    scorers = build_scorers(scorer_cfg)

    baseline_run = run_config(dataset, baseline_cfg, scorers, pricing)
    candidate_run = run_config(dataset, candidate_cfg, scorers, pricing)

    report = build_report(
        dataset, baseline_run, candidate_run,
        scorer_cfg, [s.describe() for s in scorers], thresholds, pricing,
    )
    markdown = render_markdown(report)

    out_dir = args.out
    files = {
        "report_json": os.path.join(out_dir, "report.json"),
        "report_md": os.path.join(out_dir, "report.md"),
        "report_html": os.path.join(out_dir, "report.html"),
        "manifest": os.path.join(out_dir, "manifest.json"),
    }
    _write(files["report_json"], json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    _write(files["report_md"], markdown)
    _write(files["report_html"], render_html(report))
    manifest = build_manifest(
        report, dataset, baseline_cfg, candidate_cfg, scorer_cfg, thresholds, pricing,
        provider_infos={
            "baseline": baseline_run.provider_info,
            "candidate": candidate_run.provider_info,
        },
        report_files=files,
    )
    execution_options = {}
    if args.max_input_bytes is not None:
        execution_options["max_input_bytes"] = args.max_input_bytes
    if args.require_request_binding:
        execution_options["require_request_binding"] = True
    if execution_options:
        manifest["execution_options"] = execution_options
    _write(files["manifest"], json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")

    verdict = report["gate"]["verdict"]
    exit_code = EXIT_PASS if verdict == "pass" else EXIT_GATE_FAIL

    print(f"{TOOL_NAME}: gate {verdict.upper()}")
    print(
        f"  rules: {report['gate']['n_rules']} evaluated, "
        f"{report['gate']['n_failed']} failed, {report['gate']['n_warned']} warned"
    )
    for rule in report["rules"]:
        if rule["verdict"] in ("fail", "warn"):
            print(f"  [{rule['verdict'].upper()}] {rule['metric']}: {rule['message']}")
    for notice in report["gate"]["notices"]:
        print(f"  note: {notice}")
    print(f"  result hash: {report['result_hash']}")
    print(f"  reports: {files['report_json']}, {files['report_md']}, {files['report_html']}")

    _emit_github_summary(markdown)
    _emit_github_outputs({
        "verdict": verdict,
        "exit-code": str(exit_code),
        "result-hash": report["result_hash"],
        "report-json": files["report_json"],
        "report-md": files["report_md"],
        "report-html": files["report_html"],
    })
    return exit_code


def _cmd_run(args: argparse.Namespace) -> int:
    """Run ONE config over the dataset — for authoring fixtures and debugging
    a side before wiring up a full gate."""
    dataset = load_dataset(args.dataset)
    cfg = load_run_config(args.config, "config")
    _require_binding(cfg, args.require_request_binding)
    scorer_cfg = load_scorer_config(args.scorers)
    pricing = load_pricing(args.pricing) if args.pricing else no_pricing()
    scorers = build_scorers(scorer_cfg)
    result = run_config(dataset, cfg, scorers, pricing)
    payload = {
        "tool": {"name": TOOL_NAME, "version": __version__},
        "dataset": {
            "name": dataset.name, "version": dataset.version, "sha256": dataset.sha256,
        },
        "run": result.summary(),
        "items": [r.to_dict() for r in result.records],
    }
    out_path = os.path.join(args.out, "run.json")
    _write(out_path, json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    print(f"{TOOL_NAME}: ran '{cfg.name}' on {result.n_items} items "
          f"({result.n_ok} ok, {result.n_errors} errors) -> {out_path}")
    if args.fail_on_errors and result.n_errors:
        print(f"{TOOL_NAME}: --fail-on-errors: {result.n_errors} item(s) failed; "
              f"diagnostics retained in {out_path}", file=sys.stderr)
        return EXIT_ERROR
    return EXIT_PASS


def _cmd_plan(args: argparse.Namespace) -> int:
    from .planning import build_request_plan

    dataset = load_dataset(args.dataset)
    config = load_run_config(args.config, "config")
    plan = build_request_plan(dataset, config)
    content = json.dumps(plan, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    out_path = os.path.join(args.out, "plan.json")
    try:
        os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
        # A plan must never replace an input or silently overwrite another receipt.
        with open(out_path, "x", encoding="utf-8", newline="\n") as fh:
            fh.write(content)
    except OSError as exc:
        raise GateConfigError(f"plan output could not be created: {out_path} ({exc})") from exc
    print(f"{TOOL_NAME}: planned {len(plan['requests'])} requests; no provider calls")
    print(f"  plan hash: {plan['plan_hash']}")
    print(f"  plan: {out_path}")
    return EXIT_PASS


def _cmd_hash(args: argparse.Namespace) -> int:
    for path in args.files:
        if not os.path.isfile(path):
            raise GateConfigError(f"file not found: {path}")
        print(f"{file_sha256(path)}  {path}")
    return EXIT_PASS



def _positive_bytes(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError:
        parsed = 0
    if parsed <= 0:
        raise argparse.ArgumentTypeError("max input bytes must be a positive integer")
    return parsed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=TOOL_NAME,
        description="Block unsafe LLM app changes: compare a candidate config "
                    "against the baseline over a golden dataset and fail on regression.",
    )
    parser.add_argument("--version", action="version", version=f"{TOOL_NAME} {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    gate = sub.add_parser("gate", help="run baseline vs candidate and enforce thresholds")
    gate.add_argument("--dataset", required=True, help="golden dataset JSON")
    gate.add_argument("--baseline", required=True, help="baseline run-config JSON")
    gate.add_argument("--candidate", required=True, help="candidate run-config JSON")
    gate.add_argument("--scorers", required=True, help="scorer-config JSON")
    gate.add_argument("--thresholds", required=True, help="thresholds JSON")
    gate.add_argument("--pricing", help="pricing-table JSON (omit: cost reported unavailable)")
    gate.add_argument("--out", default="out", help="output directory (default: out)")
    gate.add_argument("--max-input-bytes", type=_positive_bytes,
                      help="maximum raw bytes per JSON input, including fixtures (default: unlimited)")
    gate.add_argument("--require-request-binding", action="store_true",
                      help="require sha256-v1 bound replay in both configs (default: not required)")
    gate.set_defaults(func=_cmd_gate)

    run = sub.add_parser("run", help="run one config over the dataset (fixture debugging)")
    run.add_argument("--dataset", required=True)
    run.add_argument("--config", required=True)
    run.add_argument("--scorers", required=True)
    run.add_argument("--pricing")
    run.add_argument("--out", default="out")
    run.add_argument("--max-input-bytes", type=_positive_bytes,
                     help="maximum raw bytes per JSON input, including fixtures (default: unlimited)")
    run.add_argument("--fail-on-errors", action="store_true",
                     help="exit 2 if any item fails, after writing run.json (default: diagnostic exit 0)")
    run.add_argument("--require-request-binding", action="store_true",
                     help="require sha256-v1 bound replay in the run config")
    run.set_defaults(func=_cmd_run)

    plan = sub.add_parser("plan", help="fingerprint rendered requests without calling a provider")
    plan.add_argument("--dataset", required=True, help="golden dataset JSON")
    plan.add_argument("--config", required=True, help="run-config JSON to render")
    plan.add_argument("--out", default="out", help="directory for a new plan.json (never overwritten)")
    plan.add_argument("--max-input-bytes", type=_positive_bytes,
                      help="maximum raw bytes per JSON input (default: unlimited)")
    plan.set_defaults(func=_cmd_plan)

    hash_cmd = sub.add_parser("hash", help="print sha256 content hashes for files")
    hash_cmd.add_argument("files", nargs="+")
    hash_cmd.set_defaults(func=_cmd_hash)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        with input_byte_limit(getattr(args, "max_input_bytes", None)):
            return args.func(args)
    except GateConfigError as exc:
        print(f"{TOOL_NAME}: configuration error: {exc}", file=sys.stderr)
        return EXIT_ERROR
    except Exception:  # never let a crash masquerade as a gate verdict
        traceback.print_exc()
        print(f"{TOOL_NAME}: internal error (see traceback above)", file=sys.stderr)
        return EXIT_ERROR


if __name__ == "__main__":
    sys.exit(main())
