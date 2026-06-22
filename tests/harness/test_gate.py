"""Tests for the pre-commit gate checks."""

from __future__ import annotations

import importlib
import os
import sys
from typing import TYPE_CHECKING

from conftest import run_cmd

import harness
from harness import gate, gitio

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


def fake_checks_clean(repo: Path, checks: object) -> list[str]:
    """Skip running real checks."""
    del repo, checks
    return []


def fake_checks_failing(repo: Path, checks: object) -> list[str]:
    """Report a failing check without running anything."""
    del repo, checks
    return ["tests failed"]


def stage(repo: Path, name: str, content: str) -> None:
    """Write a file inside the repo and stage it."""
    target = repo / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    run_cmd(["git", "add", name], repo)


def test_staged_files_and_added_lines(git_repo: Path) -> None:
    """Staged paths and added diff lines are reported."""
    stage(git_repo, "pkg/a.py", "x = 1\n")
    assert gitio.staged_files(git_repo) == ["pkg/a.py"]
    assert "x = 1" in gitio.staged_added_lines(git_repo)


def test_clean_git_env_drops_hook_variables(monkeypatch: pytest.MonkeyPatch) -> None:
    """GIT_* variables exported to hooks are stripped; everything else survives."""
    monkeypatch.setenv("GIT_DIR", "/somewhere/.git")
    monkeypatch.setenv("GIT_INDEX_FILE", "/somewhere/index")
    env = gitio.clean_git_env()
    assert "GIT_DIR" not in env
    assert "GIT_INDEX_FILE" not in env
    assert env["PATH"] == os.environ["PATH"]


def test_run_git_ignores_poisoned_hook_env(monkeypatch: pytest.MonkeyPatch, git_repo: Path) -> None:
    """Gate git calls target the given repo even when hook env points elsewhere."""
    monkeypatch.setenv("GIT_DIR", str(git_repo / "does-not-exist" / ".git"))
    stage(git_repo, "pkg/a.py", "x = 1\n")
    assert gitio.staged_files(git_repo) == ["pkg/a.py"]


def test_run_checks_reports_only_failures(tmp_path: Path) -> None:
    """Failing check commands are reported; passing ones are not."""
    failures = gate.run_checks(tmp_path, (("sanity", ("false",)), ("noop", ("true",))))
    assert len(failures) == 1
    assert failures[0].startswith("sanity failed:")


def test_run_verify_runs_the_full_check_set(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """run_verify surfaces failures from the full check set."""
    monkeypatch.setattr(gate, "run_checks", fake_checks_failing)
    assert "tests failed" in gate.run_verify(tmp_path)


def test_staged_preferences_checks_python_files(git_repo: Path) -> None:
    """Staged Python files are preferences-checked; test files skip the count limit."""
    stage(git_repo, "pkg/mod.py", "secret = 1\nhidden_thing = 2\n_bad = 3\n")
    stage(git_repo, "pkg/test_mod.py", "def a():\n    return 1\n\n\ndef b():\n    return 2\n")
    stage(git_repo, "pkg/notes.md", "not python\n")
    problems = gate.staged_preferences_violations(git_repo)
    assert len(problems) == 1
    assert "'_bad'" in problems[0]


def test_staged_preferences_enforces_function_limit(monkeypatch: pytest.MonkeyPatch, git_repo: Path) -> None:
    """Non-test Python files respect the function count limit."""
    monkeypatch.setattr(gate.preferences, "MAX_FUNCTIONS_PER_FILE", 1)
    stage(git_repo, "pkg/big.py", "def a():\n    return 1\n\n\ndef b():\n    return 2\n")
    problems = gate.staged_preferences_violations(git_repo)
    assert problems == ["pkg/big.py: 2 top-level functions exceeds limit 1; split the module"]


def test_staged_preferences_skipped_without_preferences(
    monkeypatch: pytest.MonkeyPatch, git_repo: Path
) -> None:
    """When preferences.py has been deleted, structural checks are skipped, not crashed."""
    monkeypatch.setattr(gate, "preferences", None)
    stage(git_repo, "pkg/mod.py", "_bad = 1\n")
    assert gate.staged_preferences_violations(git_repo) == []


def test_gate_imports_cleanly_without_preferences(monkeypatch: pytest.MonkeyPatch) -> None:
    """Deleting preferences.py does not break importing the gate; preferences becomes None."""
    monkeypatch.delattr(harness, "preferences", raising=False)
    monkeypatch.setitem(sys.modules, "harness.preferences", None)
    importlib.reload(gate)
    assert gate.preferences is None
    monkeypatch.undo()
    importlib.reload(gate)
    assert gate.preferences is not None


def test_staged_preferences_skips_deletions(git_repo: Path) -> None:
    """Deleted Python files are not preferences-checked."""
    stage(git_repo, "pkg/old.py", "value = 1\n")
    run_cmd(["git", "commit", "-q", "-m", "add file"], git_repo)
    run_cmd(["git", "rm", "-q", "pkg/old.py"], git_repo)
    assert gate.staged_preferences_violations(git_repo) == []


def test_run_gate_blocks_protected_paths_under_loop(monkeypatch: pytest.MonkeyPatch, git_repo: Path) -> None:
    """Under the loop, protected paths are blocked."""
    monkeypatch.setenv("RALPH_LOOP", "1")
    monkeypatch.setattr(gate, "run_checks", fake_checks_clean)
    stage(git_repo, "harness/util.py", "value = 1\n")
    problems = gate.run_gate(git_repo)
    assert "protected path modified: harness/util.py" in problems


def test_run_gate_allows_editing_preferences_under_loop(
    monkeypatch: pytest.MonkeyPatch, git_repo: Path
) -> None:
    """The loop may edit the user-tunable preferences.py even though harness/* is protected."""
    monkeypatch.setenv("RALPH_LOOP", "1")
    monkeypatch.setattr(gate, "run_checks", fake_checks_clean)
    stage(git_repo, "harness/preferences.py", "VALUE = 1\n")
    assert "protected path modified: harness/preferences.py" not in gate.run_gate(git_repo)


def test_run_gate_skips_containment_for_humans(monkeypatch: pytest.MonkeyPatch, git_repo: Path) -> None:
    """Without RALPH_LOOP, a human may touch protected paths; quality checks still run."""
    monkeypatch.delenv("RALPH_LOOP", raising=False)
    monkeypatch.setattr(gate, "run_checks", fake_checks_clean)
    stage(git_repo, "harness/util.py", "value = 1\n")
    assert gate.run_gate(git_repo) == []


def test_run_gate_allows_unprotected_paths_under_loop(
    monkeypatch: pytest.MonkeyPatch, git_repo: Path
) -> None:
    """Under the loop, commits touching only unprotected paths pass."""
    monkeypatch.setenv("RALPH_LOOP", "1")
    monkeypatch.setattr(gate, "run_checks", fake_checks_clean)
    stage(git_repo, "apps/feature.ts", "const x = 1\n")
    stage(git_repo, "pkg/ok.py", "y = 2\n")
    stage(git_repo, "docs/x.md", "note\n")
    assert gate.run_gate(git_repo) == []


def test_run_gate_flags_banned_patterns_under_loop(monkeypatch: pytest.MonkeyPatch, git_repo: Path) -> None:
    """Under the loop, banned escape-hatch patterns are flagged in added lines."""
    monkeypatch.setenv("RALPH_LOOP", "1")
    monkeypatch.setattr(gate, "run_checks", fake_checks_clean)
    stage(git_repo, "pkg/ok.py", "marker = 'eslint-disable'\n")
    problems = gate.run_gate(git_repo)
    assert any("banned pattern 'eslint-disable'" in problem for problem in problems)


def test_run_gate_always_runs_checks(monkeypatch: pytest.MonkeyPatch, git_repo: Path) -> None:
    """Lint and test checks run on every commit regardless of paths."""
    monkeypatch.setattr(gate, "run_checks", fake_checks_failing)
    stage(git_repo, "anywhere/file.py", "z = 3\n")
    problems = gate.run_gate(git_repo)
    assert "tests failed" in problems
