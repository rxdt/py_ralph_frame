"""Tests for the ralph command-line interface."""

from __future__ import annotations

import subprocess
import sys
from typing import TYPE_CHECKING

from conftest import run_cmd

from harness import cli

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    import pytest


def passthrough_skip_uv(real: Callable[..., object], calls: list[tuple[str, ...]]) -> Callable[..., object]:
    """Record every command and run it for real, but stub out the slow `uv sync`."""

    def runner(
        args: tuple[str, ...], check: bool = False, capture_output: bool = False, cwd: str | None = None
    ) -> object:
        calls.append(tuple(args))
        if tuple(args[:2]) == ("uv", "sync"):
            return subprocess.CompletedProcess(list(args), 0)
        return real(args, check=check, capture_output=capture_output, cwd=cwd)

    return runner


def fake_gate_clean(repo: Path) -> list[str]:
    """Report a clean gate without running anything."""
    del repo
    return []


def fake_gate_problems(repo: Path) -> list[str]:
    """Report one gate violation without running anything."""
    del repo
    return ["protected path modified: harness/x.py"]


def test_gate_command_clean(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """A clean gate exits 0."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setitem(cli.GATES, "gate", fake_gate_clean)
    assert cli.main(["gate"]) == 0


def test_gate_command_problems(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Gate violations exit 1."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setitem(cli.GATES, "gate", fake_gate_problems)
    assert cli.main(["gate"]) == 1


def test_verify_command_problems(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """The verify command reports violations and exits 1."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setitem(cli.GATES, "verify", fake_gate_problems)
    assert cli.main(["verify"]) == 1


def test_install_syncs_deps_and_sets_hooks(monkeypatch: pytest.MonkeyPatch, git_repo: Path) -> None:
    """Install syncs dependencies and points git at the tracked hooks directory."""
    monkeypatch.chdir(git_repo)
    calls: list[tuple[str, ...]] = []
    monkeypatch.setattr(cli.subprocess, "run", passthrough_skip_uv(subprocess.run, calls))
    assert cli.main(["install"]) == 0
    assert ("uv", "sync") in calls
    monkeypatch.undo()
    out = run_cmd(["git", "config", "core.hooksPath"], git_repo)
    assert out.strip() == ".githooks"


def test_install_resets_project(monkeypatch: pytest.MonkeyPatch, git_repo: Path) -> None:
    """install <name> syncs deps, resets the [project] table, strips metadata, and sets hooks."""
    monkeypatch.chdir(git_repo)
    (git_repo / "pyproject.toml").write_text(
        '[project]\nname = "scaffold"\nauthors = [{ name = "rxdt" }]\n\n[tool.ruff]\nline-length = 110\n',
        encoding="utf-8",
    )
    calls: list[tuple[str, ...]] = []
    monkeypatch.setattr(cli.subprocess, "run", passthrough_skip_uv(subprocess.run, calls))
    assert cli.main(["install", "demo"]) == 0
    assert ("uv", "sync") in calls
    monkeypatch.undo()
    text = (git_repo / "pyproject.toml").read_text(encoding="utf-8")
    assert 'name = "demo"' in text
    assert "rxdt" not in text
    assert "[tool.ruff]" in text
    out = run_cmd(["git", "config", "core.hooksPath"], git_repo)
    assert out.strip() == ".githooks"


def test_status_reports_no_runs(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """status reports when no registry exists, through the CLI dispatch."""
    monkeypatch.chdir(tmp_path)
    assert cli.main(["status"]) == 0
    assert "no runs recorded" in capsys.readouterr().out


def test_status_prints_table(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """status prints the registry rows as an aligned table."""
    registry = tmp_path / "scratchpad" / "ralph_runs.tsv"
    registry.parent.mkdir(parents=True)
    registry.write_text("iteration\tstatus\n1\texited\n", encoding="utf-8")
    assert cli.run_status(tmp_path) == 0
    out = capsys.readouterr().out
    assert "iteration" in out
    assert "exited" in out


def test_usage_for_unknown_command(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Unknown commands print usage and exit 2."""
    monkeypatch.chdir(tmp_path)
    assert cli.main(["bogus"]) == 2
    assert cli.main([]) == 2


def test_main_reads_sys_argv(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Without an explicit argv the CLI reads sys.argv."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["ralph", "bogus"])
    assert cli.main() == 2
