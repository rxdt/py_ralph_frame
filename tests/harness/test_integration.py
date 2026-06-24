"""Integration tests: containment runs through a real git pre-commit hook.

These commit for real through a hook that calls the actual `harness.gate` containment. They
show what `RALPH_LOOP` and the hook do end to end — and where containment can be bypassed.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from conftest import run_cmd

REPO_ROOT = Path(__file__).resolve().parents[2]

GATE_HOOK = (
    "import os, sys, pathlib\n"
    f"sys.path.insert(0, {str(REPO_ROOT)!r})\n"
    "from harness import gate\n"
    "repo = pathlib.Path.cwd()\n"
    "loop = os.environ.get('RALPH_LOOP')\n"
    "problems = gate.agent_violations(repo, gate.staged_files(repo)) if loop else []\n"
    "for problem in problems:\n"
    "    sys.stderr.write(problem + '\\n')\n"
    "sys.exit(1 if problems else 0)\n"
)


def arm_gate_hook(repo: Path) -> None:
    """Install a real pre-commit hook that runs the harness containment check."""
    hooks = repo / ".githooks"
    hooks.mkdir()
    (hooks / "gate_hook.py").write_text(GATE_HOOK, encoding="utf-8")
    pre_commit = hooks / "pre-commit"
    pre_commit.write_text(
        f'#!/bin/sh\nexec "{sys.executable}" "{hooks / "gate_hook.py"}"\n', encoding="utf-8"
    )
    pre_commit.chmod(0o755)
    run_cmd(["git", "config", "core.hooksPath", ".githooks"], repo)


def stage_forbidden(repo: Path) -> None:
    """Write and stage a file under a forbidden path."""
    (repo / "harness").mkdir()
    (repo / "harness" / "evil.py").write_text("value = 1\n", encoding="utf-8")
    run_cmd(["git", "add", "harness/evil.py"], repo)


def attempt_commit(repo: Path, message: str, loop: bool, no_verify: bool) -> subprocess.CompletedProcess[str]:
    """Try a commit with optional RALPH_LOOP in the env and optional --no-verify."""
    env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    if loop:
        env["RALPH_LOOP"] = "1"
    args = ["git", "commit", "-q", "-m", message]
    if no_verify:
        args.append("--no-verify")
    return subprocess.run(args, cwd=repo, capture_output=True, text=True, check=False, env=env)


def test_hook_blocks_forbidden_path_under_loop(git_repo: Path) -> None:
    """RALPH_LOOP=1 + active hook: a real commit touching a forbidden path is rejected."""
    arm_gate_hook(git_repo)
    stage_forbidden(git_repo)
    result = attempt_commit(git_repo, "evil", loop=True, no_verify=False)
    assert result.returncode != 0
    assert "forbidden path modified: harness/evil.py" in result.stderr


def test_hook_allows_forbidden_path_without_loop(git_repo: Path) -> None:
    """Without RALPH_LOOP (a human), the same commit is allowed — containment is loop-only."""
    arm_gate_hook(git_repo)
    stage_forbidden(git_repo)
    result = attempt_commit(git_repo, "human edit", loop=False, no_verify=False)
    assert result.returncode == 0


def test_no_verify_bypasses_the_hook(git_repo: Path) -> None:
    """--no-verify skips the hook entirely: containment is best-effort, not a jail."""
    arm_gate_hook(git_repo)
    stage_forbidden(git_repo)
    result = attempt_commit(git_repo, "bypass", loop=True, no_verify=True)
    assert result.returncode == 0
