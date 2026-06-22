"""Git subprocess helpers with hook-safe environment handling."""

from __future__ import annotations

import os
import subprocess
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


def clean_git_env() -> dict[str, str]:
    """Return the environment without GIT_* variables.

    Git exports GIT_DIR and GIT_INDEX_FILE to hook processes; anything the
    gate spawns must not inherit them, or nested git calls (including the
    test suite's own fixtures) operate on the committing repo instead.
    """
    return {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}


def run_git(repo: Path, args: list[str]) -> str:
    """Run a git command in the repo and return its stdout."""
    command = ["git", "-C", str(repo)]
    command.extend(args)
    result = subprocess.run(command, capture_output=True, text=True, check=True, env=clean_git_env())
    return result.stdout


def staged_files(repo: Path) -> list[str]:
    """Return paths staged for commit, relative to the repo root."""
    out = run_git(repo, ["diff", "--cached", "--name-only", "--diff-filter=ACMRD"])
    return [line for line in out.splitlines() if line]


def staged_added_lines(repo: Path) -> list[str]:
    """Return content lines added in the staged diff, without the leading marker."""
    out = run_git(repo, ["diff", "--cached", "--unified=0"])
    return [line[1:] for line in out.splitlines() if line.startswith("+") and not line.startswith("+++")]
