"""Archived planning proposals must never turn unconfirmed choices into authority."""

import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "docs/acceleration/2026-09-10"
SCRIPT = BUNDLE / "scripts/unbundle.py"
spec = importlib.util.spec_from_file_location("unbundle", SCRIPT)
unbundle = importlib.util.module_from_spec(spec)
spec.loader.exec_module(unbundle)


def inputs():
    catalog = {"analysis": {"project": "test", "analyzed_head": "historical"}, "decisions": [
        {"id": "D1", "requires_human": True, "options": [{"id": "D1-A", "tasks": ["A"]}]},
        {"id": "D2", "requires_human": False, "options": [{"id": "D2-A", "tasks": ["C"]}]},
    ]}
    issues = {"issues": [
        {"id": key, "title": key, "priority": "P1", "milestone": "M0", "summary": key,
         "depends_on": deps, "decision_ids": decisions}
        for key, deps, decisions in [("A", [], ["D1"]), ("B", ["A"], []), ("C", ["B"], ["D2"])]
    ]}
    export = {"project": "test", "decisions": [
        {"decision_id": "D1", "selected_option_id": "D1-A", "confirmed": False},
    ]}
    return catalog, issues, export


def test_unconfirmed_selection_is_visible_without_mutating_catalogs():
    catalog, issues, export = inputs()
    before = copy.deepcopy((catalog, issues, export))
    ordered, blockers, _ = unbundle.validate_and_select(catalog, issues, export)
    assert [task["id"] for task in ordered] == ["A"]
    assert ordered[0]["bundle_status"] == "blocked-human-decision"
    assert ordered[0]["bundle_blocker"] == "D1"
    assert "not human-confirmed" in blockers[0]
    assert (catalog, issues, export) == before


def test_human_block_propagates_through_all_dependents():
    catalog, issues, export = inputs()
    export["decisions"].append({"decision_id": "D2", "selected_option_id": "D2-A"})
    ordered, _, _ = unbundle.validate_and_select(catalog, issues, export)
    assert [task["id"] for task in ordered] == ["A", "B", "C"]
    assert all(task["bundle_status"] == "blocked-human-decision" for task in ordered)
    assert all(task["bundle_blocker"] == "D1" for task in ordered)


@pytest.mark.parametrize("confirmation", ["false", "true", 1, {}, None])
def test_only_literal_true_confirms_human_choice(confirmation):
    catalog, issues, export = inputs()
    export["decisions"][0]["confirmed"] = confirmation
    ordered, _, _ = unbundle.validate_and_select(catalog, issues, export)
    assert [task["id"] for task in ordered] == ["A"]
    assert ordered[0]["bundle_status"] == "blocked-human-decision"


def test_confirmation_without_selected_option_does_not_unblock_dependency():
    catalog, issues, export = inputs()
    export["decisions"][0].update(selected_option_id=None, confirmed=True)
    export["decisions"].append({"decision_id": "D2", "selected_option_id": "D2-A"})
    ordered, _, _ = unbundle.validate_and_select(catalog, issues, export)
    assert all(task["bundle_status"] == "blocked-human-decision" for task in ordered)


def test_confirmed_dependency_releases_selected_chain():
    catalog, issues, export = inputs()
    export["decisions"][0]["confirmed"] = True
    export["decisions"].append({"decision_id": "D2", "selected_option_id": "D2-A"})
    ordered, blockers, _ = unbundle.validate_and_select(catalog, issues, export)
    assert [task["id"] for task in ordered] == ["A", "B", "C"]
    assert not blockers
    assert all(task.get("bundle_status", "ready") == "ready" for task in ordered)


def test_unconfirmed_option_blocks_task_even_without_redundant_decision_metadata():
    catalog, issues, export = inputs()
    issues["issues"][0]["decision_ids"] = []
    ordered, _, _ = unbundle.validate_and_select(catalog, issues, export)
    assert ordered[0]["bundle_blocker"] == "D1"


def test_missing_dependency_has_named_error():
    catalog, issues, export = inputs()
    export["decisions"][0]["confirmed"] = True
    issues["issues"][0]["depends_on"] = ["missing"]
    with pytest.raises(SystemExit, match="A.*unknown task.*missing"):
        unbundle.validate_and_select(catalog, issues, export)


def test_dependency_cycle_still_fails_closed():
    catalog, issues, export = inputs()
    export["decisions"][0]["confirmed"] = True
    issues["issues"][0]["depends_on"] = ["C"]
    with pytest.raises(SystemExit, match="cycle"):
        unbundle.validate_and_select(catalog, issues, export)


def test_cli_requires_explicit_reconstructed_bundle(tmp_path):
    (tmp_path / ".git").mkdir()
    result = subprocess.run([sys.executable, str(SCRIPT), "--repo", str(tmp_path),
                             "--decisions", "unused.json"], capture_output=True, text=True)
    assert result.returncode == 2
    assert "required: --bundle" in result.stderr


def test_cli_preview_preserves_human_block_and_writes_nothing(tmp_path):
    catalog, issues, export = inputs()
    repo, bundle = tmp_path / "repo", tmp_path / "bundle"
    (repo / ".git").mkdir(parents=True)
    for path, data in [(bundle / "01-decisions/decision-catalog.json", catalog),
                       (bundle / "02-roadmap/issue-catalog.json", issues),
                       (tmp_path / "selected.json", export)]:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data), encoding="utf-8")
    result = subprocess.run([sys.executable, str(SCRIPT), "--repo", str(repo),
                             "--bundle", str(bundle), "--decisions", str(tmp_path / "selected.json")],
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert "blocked-human-decision" in result.stdout
    assert not (repo / ".planning").exists()


@pytest.mark.parametrize("output", [".", ".planning", "../outside", "src"])
def test_force_scaffold_output_boundary_remains_restricted(tmp_path, output):
    with pytest.raises(SystemExit):
        unbundle.resolve_output_path(tmp_path.resolve(), Path(output))


def test_snapshot_identity_prose_matches_schema():
    schema = json.loads((BUNDLE / "04-implementation/run-snapshot.schema.json").read_text())
    text = (BUNDLE / "03-architecture/target-evidence-architecture.md").read_text()
    assert "snapshot_sha256" in schema["required"]
    assert '"snapshot_sha256": "sha256:..."' in text
    assert "snapshot_id" not in text


def test_dependency_only_human_block_is_listed_in_summary():
    catalog, issues, export = inputs()
    export["decisions"] = [{"decision_id": "D2", "selected_option_id": "D2-A"}]
    ordered, blockers, notes = unbundle.validate_and_select(catalog, issues, export)
    assert any(reason.startswith("D1:") for reason in blockers)
    assert "None in the selected task set" not in unbundle.render_workplan(export, ordered, blockers, notes)


def test_multiple_human_blockers_are_preserved_in_dependency_order():
    catalog, issues, export = inputs()
    catalog["decisions"].append({"id": "D3", "requires_human": True,
                                 "options": [{"id": "D3-A", "tasks": ["B"]}]})
    export["decisions"] += [{"decision_id": "D3", "selected_option_id": "D3-A"},
                             {"decision_id": "D2", "selected_option_id": "D2-A"}]
    ordered, _, _ = unbundle.validate_and_select(catalog, issues, export)
    assert ordered[0]["bundle_blocker"] == "D1"
    assert ordered[1]["bundle_blocker"] == "D1, D3"
    assert ordered[2]["bundle_blocker"] == "D1, D3"


def test_unknown_task_decision_has_named_error():
    catalog, issues, export = inputs()
    export["decisions"][0]["confirmed"] = True
    issues["issues"][0]["decision_ids"] = ["missing"]
    with pytest.raises(SystemExit, match="A.*unknown decision.*missing"):
        unbundle.validate_and_select(catalog, issues, export)
