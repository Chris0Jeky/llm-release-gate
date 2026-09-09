#!/usr/bin/env python3
"""Turn an exported decision file into a repo-local workplan.

Dry-run by default. With --scaffold, writes only planning files under the chosen
output directory; it never edits product source, calls the network, creates issues,
commits, tags or releases.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import shutil
import sys
from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Any


def load_json(path: pathlib.Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"cannot read {path}: {exc}") from exc


def topo_sort(selected: dict[str, dict]) -> list[dict]:
    indegree = {key: 0 for key in selected}
    children: dict[str, list[str]] = defaultdict(list)
    for key, issue in selected.items():
        for dep in issue.get("depends_on", []):
            if dep in selected:
                indegree[key] += 1
                children[dep].append(key)
    queue = deque(sorted((k for k, n in indegree.items() if n == 0), key=lambda k: (selected[k]["priority"], k)))
    result = []
    while queue:
        key = queue.popleft()
        result.append(selected[key])
        for child in sorted(children[key]):
            indegree[child] -= 1
            if indegree[child] == 0:
                queue.append(child)
    if len(result) != len(selected):
        cycle = sorted(k for k, n in indegree.items() if n)
        raise SystemExit(f"task dependency cycle detected: {cycle}")
    return result


def validate_and_select(catalog: dict, issues: dict, export: dict) -> tuple[list[dict], list[str], list[str]]:
    if export.get("project") != catalog["analysis"]["project"]:
        raise SystemExit("decision export project does not match catalog")
    decision_by_id = {d["id"]: d for d in catalog["decisions"]}
    option_by_id = {o["id"]: (d, o) for d in catalog["decisions"] for o in d["options"]}
    selected_task_ids: set[str] = set()
    blocked_reasons: list[str] = []
    notes: list[str] = []

    seen: set[str] = set()
    for selection in export.get("decisions", []):
        did = selection.get("decision_id")
        if did not in decision_by_id:
            raise SystemExit(f"unknown decision id {did!r}")
        if did in seen:
            raise SystemExit(f"duplicate decision selection {did}")
        seen.add(did)
        oid = selection.get("selected_option_id")
        if oid is None:
            if decision_by_id[did].get("requires_human"):
                blocked_reasons.append(f"{did}: no option selected")
            continue
        if oid not in option_by_id or option_by_id[oid][0]["id"] != did:
            raise SystemExit(f"option {oid!r} does not belong to {did}")
        decision, option = option_by_id[oid]
        if decision.get("requires_human") and not selection.get("confirmed", False):
            blocked_reasons.append(f"{did}: {oid} is selected but not human-confirmed")
        else:
            selected_task_ids.update(option.get("tasks", []))
        note = str(selection.get("note", "")).strip()
        if note:
            notes.append(f"{did}: {note}")

    issue_by_id = {x["id"]: x for x in issues["issues"]}
    unknown_tasks = selected_task_ids - set(issue_by_id)
    if unknown_tasks:
        raise SystemExit(f"decision catalog references unknown tasks: {sorted(unknown_tasks)}")

    # Include dependencies recursively; a dependency can itself remain blocked by an
    # unconfirmed human decision and will be marked below.
    stack = list(selected_task_ids)
    while stack:
        task_id = stack.pop()
        for dep in issue_by_id[task_id].get("depends_on", []):
            if dep not in selected_task_ids:
                selected_task_ids.add(dep)
                stack.append(dep)

    selected = {key: issue_by_id[key] for key in selected_task_ids}
    ordered = topo_sort(selected)

    confirmed = {s["decision_id"]: bool(s.get("confirmed")) for s in export.get("decisions", [])}
    for task in ordered:
        for did in task.get("decision_ids", []):
            d = decision_by_id[did]
            if d.get("requires_human") and not confirmed.get(did, False):
                task = dict(task)
                task["bundle_status"] = "blocked-human-decision"
                task["bundle_blocker"] = did
                selected[task["id"]] = task
    ordered = topo_sort(selected)
    return ordered, blocked_reasons, notes


def render_workplan(export: dict, ordered: list[dict], blockers: list[str], notes: list[str]) -> str:
    lines = [
        "# Selected llm-release-gate workplan",
        "",
        f"Generated from deck export for analysis head `{export.get('analysis_head', 'unknown')}`.",
        "Live repository state and policy remain authoritative.",
        "",
        "## Human decision blockers",
        "",
    ]
    lines.extend(f"- {x}" for x in blockers or ["None in the selected task set."])
    if notes:
        lines += ["", "## Owner notes", ""] + [f"- {x}" for x in notes]
    lines += ["", "## Dependency-ordered tasks", ""]
    for idx, task in enumerate(ordered, 1):
        status = task.get("bundle_status", "ready")
        lines += [
            f"### {idx}. {task['id']} — {task['title']}",
            "",
            f"- Priority: `{task['priority']}`",
            f"- Milestone: `{task['milestone']}`",
            f"- Status: `{status}`",
            f"- Depends on: {', '.join(task.get('depends_on', [])) or 'none'}",
        ]
        if task.get("bundle_blocker"):
            lines.append(f"- Human blocker: `{task['bundle_blocker']}`")
        lines += ["", task["summary"], "", "Acceptance:"]
        lines.extend(f"- [ ] {x}" for x in task.get("acceptance", []))
        lines += ["", "Proving checks:"]
        lines.extend(f"- {x}" for x in task.get("tests", []))
        lines.append("")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=pathlib.Path, required=True, help="live repository root")
    parser.add_argument("--decisions", type=pathlib.Path, required=True, help="deck JSON export")
    parser.add_argument("--bundle", type=pathlib.Path, default=pathlib.Path(__file__).resolve().parents[1])
    parser.add_argument("--output", default=".planning/llm-release-gate-acceleration")
    parser.add_argument("--scaffold", action="store_true", help="write planning files")
    parser.add_argument("--force", action="store_true", help="replace an existing planning output")
    args = parser.parse_args()

    repo = args.repo.resolve()
    if not (repo / ".git").exists():
        raise SystemExit(f"{repo} does not look like a Git checkout")
    catalog = load_json(args.bundle / "01-decisions/decision-catalog.json")
    issues = load_json(args.bundle / "02-roadmap/issue-catalog.json")
    export = load_json(args.decisions)
    ordered, blockers, notes = validate_and_select(catalog, issues, export)
    plan = render_workplan(export, ordered, blockers, notes)

    print(plan)
    if not args.scaffold:
        print("Dry run only. Add --scaffold to write repo-local planning files.", file=sys.stderr)
        return 0

    out = repo / args.output
    if out.exists():
        if not args.force:
            raise SystemExit(f"output already exists: {out}; use --force to replace")
        shutil.rmtree(out)
    out.mkdir(parents=True)
    (out / "WORKPLAN.md").write_text(plan, encoding="utf-8", newline="\n")
    (out / "SELECTED_DECISIONS.json").write_text(json.dumps(export, indent=2) + "\n", encoding="utf-8", newline="\n")
    (out / "SELECTED_TASKS.json").write_text(json.dumps({"schema_version":"1.0","tasks":ordered}, indent=2) + "\n", encoding="utf-8", newline="\n")
    (out / "BUNDLE_SOURCE.json").write_text(json.dumps({
        "bundle_analysis_head": catalog["analysis"]["analyzed_head"],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "note": "Planning scaffold only; live repository state is authoritative."
    }, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"Wrote planning scaffold to {out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
