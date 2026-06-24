"""Git subprocess helpers with hook-safe environment handling."""

from __future__ import annotations

import os
import subprocess
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


def clean_git_env() -> dict[str, str]:
    """Copy of os.environ with every GIT_* variable removed.

    A git hook runs with GIT_DIR and GIT_INDEX_FILE already set to the repo
    doing the commit. Those vars override `git -C <path>`, so any git command
    we spawn would read/write that committing repo instead of <path> -- and the
    test fixtures' temp repos would clobber the real one. Dropping GIT_* makes
    `-C <path>` win again.
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
    out = run_git(repo, ["diff", "--cached", "--name-only", "--no-renames", "--diff-filter=ACMRD"])
    return [line for line in out.splitlines() if line]


def staged_added_lines(repo: Path) -> list[str]:
    """Return content lines added in the staged diff, without the leading marker."""
    out = run_git(repo, ["diff", "--cached", "--unified=0"])
    return [line[1:] for line in out.splitlines() if line.startswith("+") and not line.startswith("+++")]
