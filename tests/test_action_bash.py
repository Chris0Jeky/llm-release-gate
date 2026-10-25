"""Action simulations need a shell that preserves native process inputs."""

from pathlib import Path

import pytest

import conftest


@pytest.mark.parametrize("git_dir", ["cmd", "bin"])
def test_windows_uses_bash_from_git_installation(tmp_path, monkeypatch, git_dir):
    install = tmp_path / "Custom Git"
    bash = install / "bin/bash.exe"
    bash.parent.mkdir(parents=True)
    bash.touch()
    git = install / git_dir / "git.exe"
    monkeypatch.setattr(conftest.sys, "platform", "win32")
    monkeypatch.setattr(conftest.shutil, "which", lambda name: (
        str(git) if name == "git" else "C:/Windows/System32/bash.exe"))
    assert conftest._find_action_bash() == str(bash)


def test_windows_finds_default_git_bash_without_git_on_path(monkeypatch):
    bash = Path("C:/Program Files/Git/bin/bash.exe")
    monkeypatch.setattr(conftest.sys, "platform", "win32")
    monkeypatch.setattr(conftest.shutil, "which", lambda name: None)
    monkeypatch.setattr(Path, "is_file", lambda path: path == bash)
    assert conftest._find_action_bash() == str(bash)


def test_windows_does_not_fall_back_to_wsl_bash(monkeypatch):
    monkeypatch.setattr(conftest.sys, "platform", "win32")
    monkeypatch.setattr(conftest.shutil, "which", lambda name: (
        "C:/Windows/System32/bash.exe" if name == "bash" else None))
    monkeypatch.setattr(Path, "is_file", lambda path: False)
    assert conftest._find_action_bash() is None


@pytest.mark.parametrize("bash", ["/bin/bash", None])
def test_posix_uses_bash_on_path(monkeypatch, bash):
    monkeypatch.setattr(conftest.sys, "platform", "linux")
    monkeypatch.setattr(conftest.shutil, "which", lambda name: bash if name == "bash" else None)
    assert conftest._find_action_bash() == bash
