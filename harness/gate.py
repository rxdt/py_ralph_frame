"""Gate and verify: staged quality checks plus loop containment.

`run_gate` is the pre-commit gate — fast lint/format for everyone, plus containment (protected
paths, banned patterns, preferences limits) for the autonomous loop when ``RALPH_LOOP`` is set
(``harness/ralph.sh`` exports it). `run_verify` is the heavier pre-push / CI pass: types, security
(semgrep), tests, and 100% coverage.
"""

from __future__ import annotations

import fnmatch
import os
import subprocess
from pathlib import PurePosixPath
from typing import TYPE_CHECKING

from harness.gitio import clean_git_env, run_git, staged_added_lines, staged_files

try:
    from harness import preferences
except ImportError:  # preferences.py is optional; humans may delete it without breaking the gate.
    preferences = None

if TYPE_CHECKING:
    from pathlib import Path

type Checks = tuple[tuple[str, tuple[str, ...]], ...]

COMMIT_CHECKS: Checks = (
    ("lint", ("uv", "run", "ruff", "check", ".")),
    ("format", ("uv", "run", "ruff", "format", "--check", ".")),
)

FULL_CHECKS: Checks = (
    ("lint", ("uv", "run", "ruff", "check", ".")),
    ("format", ("uv", "run", "ruff", "format", "--check", ".")),
    ("types", ("uv", "run", "pyright")),
    ("pylint", ("uv", "run", "pylint", "harness", "src")),
    (
        "security",
        ("uv", "run", "semgrep", "scan", "--config", "auto", "--config", "p/secrets", "--error", "--quiet"),
    ),
    ("tests", ("uv", "run", "pytest")),
)

PROTECTED_PATHS = (
    "AGENTS.md",
    "harness/*",
    "tests/harness/*",
    ".githooks/*",
    ".github/*",
    "pyproject.toml",
)

# preferences.py is the user-tunable knobs file: optional, and the loop is allowed to edit it.
UNPROTECTED_PATHS = ("harness/preferences.py",)

FORBIDDEN_PATTERNS = (
    "noqa",
    "type: ignore",
    "type:ignore",
    "pragma: no cover",
    "eslint-disable",
    "ts-ignore",
    "ts-nocheck",
    "ts-expect-error",
    "--no-verify",
    "hooksPath",
    "pytest.mark.skip",
    "fail_under",
    "cov-fail-under",
    "pylint:",
    "pytest.mark.xfail",
)


def staged_preferences_violations(repo: Path) -> list[str]:
    """Run structural style checks on staged Python files; skipped if preferences.py is absent."""
    if preferences is None:
        return []
    out = run_git(repo, ["diff", "--cached", "--name-only", "--diff-filter=ACMR"])
    problems: list[str] = []
    for path in out.splitlines():
        if not path.endswith(".py"):
            continue
        name = PurePosixPath(path).name
        is_test_file = name.startswith("test_") or name == "conftest.py"
        limit = 0 if is_test_file else preferences.MAX_FUNCTIONS_PER_FILE
        problems.extend(preferences.preferences_violations(path, run_git(repo, ["show", f":{path}"]), limit))
    return problems


def agent_violations(repo: Path, files: list[str]) -> list[str]:
    """Flag protected-path, banned-pattern, and preferences issues for a loop commit."""
    problems = [
        f"protected path modified: {path}"
        for path in files
        if any(fnmatch.fnmatch(path, pattern) for pattern in PROTECTED_PATHS)
        and path not in UNPROTECTED_PATHS
    ]
    problems.extend(
        f"banned pattern '{pattern}' in added line: {line.strip()}"
        for line in staged_added_lines(repo)
        for pattern in FORBIDDEN_PATTERNS
        if pattern in line
    )
    problems.extend(staged_preferences_violations(repo))
    return problems


def run_checks(repo: Path, checks: Checks) -> list[str]:
    """Run each named check command; return one failure entry per command that fails."""
    failures: list[str] = []
    env = clean_git_env()
    for name, command in checks:
        result = subprocess.run(command, cwd=repo, capture_output=True, text=True, check=False, env=env)
        if result.returncode != 0:
            failures.append(f"{name} failed:\n{result.stdout}{result.stderr}")
    return failures


def run_gate(repo: Path) -> list[str]:
    """Pre-commit gate: fast lint/format for everyone, plus containment for the loop."""
    problems: list[str] = []
    if os.environ.get("RALPH_LOOP"):
        problems.extend(agent_violations(repo, staged_files(repo)))
    problems.extend(run_checks(repo, COMMIT_CHECKS))
    return problems


def run_verify(repo: Path) -> list[str]:
    """Pre-push / CI verification: lint, format, types, security, tests, and coverage."""
    return run_checks(repo, FULL_CHECKS)
