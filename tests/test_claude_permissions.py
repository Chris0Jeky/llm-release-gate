"""Static repository permission contract, not a Claude runtime matcher test."""

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def settings():
    return json.loads((ROOT / ".claude/settings.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("rule", ["Bash(rg:*)", "Bash(gh :*)"])
def test_unsafe_or_inert_shell_allow_is_absent(rule):
    assert rule not in settings()["permissions"]["allow"]


def test_permission_repair_does_not_expand_repo_authority():
    config = settings()
    permissions = config["permissions"]
    assert "defaultMode" not in config
    assert "defaultMode" not in permissions
    assert not any(rule.startswith("Bash(gh") for rule in permissions["allow"])
    assert {"Read(*)", "Grep(*)", "Glob(*)"} <= set(permissions["allow"])
    assert {"Bash(git push --force:*)", "Bash(git push -f:*)",
            "Bash(rm -rf /:*)", "Bash(rm -rf ~:*)", "Bash(sudo *)",
            "Bash(curl * | sh*)", "Bash(wget * | sh*)"} <= set(permissions["deny"])


def test_permission_reference_respects_current_owner_scope():
    reference = (ROOT / "docs/acceleration/2026-09-10/04-implementation/issue-20-and-sentinel-patches.md")
    text = reference.read_text(encoding="utf-8")
    assert "Keep `defaultMode: acceptEdits`" not in text
    assert "no project `defaultMode`" in text
    assert "not a runtime permission-matcher proof" in text
