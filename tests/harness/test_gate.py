"""Tests for the pre-commit gate checks."""

from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path

import pytest
from conftest import run_cmd

import harness
from harness import gate, gitio

REPO_ROOT = Path(__file__).resolve().parents[2]


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


def test_run_gate_blocks_forbidden_paths_under_loop(monkeypatch: pytest.MonkeyPatch, git_repo: Path) -> None:
    """Under the loop, forbidden paths are blocked."""
    monkeypatch.setenv("RALPH_LOOP", "1")
    monkeypatch.setattr(gate, "run_checks", fake_checks_clean)
    stage(git_repo, "harness/util.py", "value = 1\n")
    problems = gate.run_gate(git_repo)
    assert "forbidden path modified: harness/util.py" in problems


def test_run_gate_blocks_preferences_under_loop(monkeypatch: pytest.MonkeyPatch, git_repo: Path) -> None:
    """preferences.py is forbidden to agents, like the rest of harness/*."""
    monkeypatch.setenv("RALPH_LOOP", "1")
    monkeypatch.setattr(gate, "run_checks", fake_checks_clean)
    stage(git_repo, "harness/preferences.py", "VALUE = 1\n")
    assert "forbidden path modified: harness/preferences.py" in gate.run_gate(git_repo)


def test_run_gate_skips_containment_for_humans(monkeypatch: pytest.MonkeyPatch, git_repo: Path) -> None:
    """Without RALPH_LOOP, a human may touch forbidden paths; quality checks still run."""
    monkeypatch.delenv("RALPH_LOOP", raising=False)
    monkeypatch.setattr(gate, "run_checks", fake_checks_clean)
    stage(git_repo, "harness/util.py", "value = 1\n")
    assert gate.run_gate(git_repo) == []


def test_run_gate_allows_allowed_paths_under_loop(monkeypatch: pytest.MonkeyPatch, git_repo: Path) -> None:
    """Under the loop, commits touching only allowed paths pass."""
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


def test_run_gate_flags_pyright_ignore_under_loop(monkeypatch: pytest.MonkeyPatch, git_repo: Path) -> None:
    """Under the loop, a pyright type-suppression is flagged like other escape hatches."""
    monkeypatch.setenv("RALPH_LOOP", "1")
    monkeypatch.setattr(gate, "run_checks", fake_checks_clean)
    stage(git_repo, "pkg/ok.py", "value = 1  # pyright: ignore\n")
    problems = gate.run_gate(git_repo)
    assert any("banned pattern 'pyright: ignore'" in problem for problem in problems)


@pytest.mark.parametrize(
    "path",
    [
        "AGENTS.md",
        ".github/ci.yml",
        ".githooks/pre-commit",
        "tests/harness/x.py",
        "pyproject.toml",
        "harness/deep/mod.py",
        # loop-control files: an agent must not rewrite its own next-iteration prompt, plan, or lockfile
        "PROMPT.md",
        "docs/plan.md",
        "uv.lock",
        # tooling-config shadow files that could override or weaken the checks set in pyproject.toml
        "pytest.ini",
        "tox.ini",
        "setup.cfg",
        ".coveragerc",
        "ruff.toml",
        ".ruff.toml",
        ".semgrepignore",
        "pyrightconfig.json",
        ".pylintrc",
        # submodule/repo-control surface: an agent must not add or repoint submodules
        ".gitmodules",
    ],
)
def test_each_forbidden_path_blocked_under_loop(
    monkeypatch: pytest.MonkeyPatch, git_repo: Path, path: str
) -> None:
    """Every FORBIDDEN_PATHS glob (including nested paths) is rejected for the loop."""
    monkeypatch.setenv("RALPH_LOOP", "1")
    monkeypatch.setattr(gate, "run_checks", fake_checks_clean)
    stage(git_repo, path, "x = 1\n")
    assert any("forbidden path modified" in problem for problem in gate.run_gate(git_repo))


@pytest.mark.parametrize("pattern", gate.FORBIDDEN_PATTERNS)
def test_each_banned_pattern_flagged_under_loop(
    monkeypatch: pytest.MonkeyPatch, git_repo: Path, pattern: str
) -> None:
    """Every FORBIDDEN_PATTERNS entry is flagged when added under the loop."""
    monkeypatch.setenv("RALPH_LOOP", "1")
    monkeypatch.setattr(gate, "run_checks", fake_checks_clean)
    stage(git_repo, "pkg/ok.py", f"value = 1  # {pattern}\n")
    assert any(f"banned pattern '{pattern}'" in problem for problem in gate.run_gate(git_repo))


def test_banned_pattern_on_removed_line_not_flagged(monkeypatch: pytest.MonkeyPatch, git_repo: Path) -> None:
    """A banned pattern only present in a deleted line is not flagged; only added lines count."""
    monkeypatch.setenv("RALPH_LOOP", "1")
    monkeypatch.setattr(gate, "run_checks", fake_checks_clean)
    stage(git_repo, "pkg/ok.py", "value = 1  # noqa\n")
    run_cmd(["git", "commit", "-q", "-m", "seed-noqa"], git_repo)
    stage(git_repo, "pkg/ok.py", "value = 1\n")  # the noqa line is removed
    assert gate.run_gate(git_repo) == []


@pytest.mark.parametrize(
    "line",
    [
        "value = 1  # NoQA is still a Ruff escape hatch\n",
        "value = 1  # PyRight: Ignore is still a type-checker escape hatch\n",
        "command = 'git commit --NO-VERIFY'\n",
        "setting = 'core.HooksPath /tmp/disabled'\n",
        "flag = 'pytest --COV-FAIL-UNDER=0'\n",
    ],
)
def test_banned_patterns_are_case_insensitive_under_loop(
    monkeypatch: pytest.MonkeyPatch, git_repo: Path, line: str
) -> None:
    """Mixed-case escape hatches are flagged too; pattern matching is case-insensitive."""
    monkeypatch.setenv("RALPH_LOOP", "1")
    monkeypatch.setattr(gate, "run_checks", fake_checks_clean)
    stage(git_repo, "pkg/ok.py", line)
    assert any("banned pattern" in problem for problem in gate.run_gate(git_repo))


def test_rename_out_of_forbidden_path_blocked_under_loop(
    monkeypatch: pytest.MonkeyPatch, git_repo: Path
) -> None:
    """Renaming a file out of harness/ still flags the forbidden source path (via --no-renames)."""
    monkeypatch.setenv("RALPH_LOOP", "1")
    monkeypatch.setattr(gate, "run_checks", fake_checks_clean)
    stage(git_repo, "harness/owned.py", "value = 1\n")
    run_cmd(["git", "commit", "-q", "-m", "seed harness file"], git_repo)
    (git_repo / "pkg").mkdir()
    run_cmd(["git", "mv", "harness/owned.py", "pkg/owned.py"], git_repo)
    assert any("forbidden path modified: harness/owned.py" in problem for problem in gate.run_gate(git_repo))


def test_commit_checks_execute_real_ruff() -> None:
    """COMMIT_CHECKS actually run ruff in the project venv and pass on the clean repo.

    This exercises the real command strings (not a mock), so a broken tool invocation —
    like the direct-.venv/bin regression — would fail here instead of hiding behind coverage.
    """
    assert gate.run_checks(REPO_ROOT, gate.COMMIT_CHECKS) == []


def test_run_gate_always_runs_checks(monkeypatch: pytest.MonkeyPatch, git_repo: Path) -> None:
    """Lint and test checks run on every commit regardless of paths."""
    monkeypatch.setattr(gate, "run_checks", fake_checks_failing)
    stage(git_repo, "anywhere/file.py", "z = 3\n")
    problems = gate.run_gate(git_repo)
    assert "tests failed" in problems
