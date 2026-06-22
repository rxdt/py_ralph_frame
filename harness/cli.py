"""Command-line interface for the ralph harness."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from harness.gate import run_gate, run_verify

GATES = {"gate": run_gate, "verify": run_verify}


def report(problems: list[str]) -> int:
    """Print any violations and return the matching process exit code."""
    for problem in problems:
        sys.stderr.write(f"gate: {problem}\n")
    if problems:
        sys.stderr.write("rejected by ralph\n")
        return 1
    sys.stderr.write("ok: passed\n")
    return 0


def reset_project(pyproject: Path, name: str) -> None:
    """Replace the scaffold's [project] table with a minimal one for the new project."""
    lines = pyproject.read_text(encoding="utf-8").splitlines(keepends=True)
    start = next(index for index, line in enumerate(lines) if line.startswith("[project]"))
    after = enumerate(lines[start + 1 :], start + 1)
    end = next((index for index, line in after if line.startswith("[")), len(lines))
    block = (
        f'[project]\nname = "{name}"\nversion = "0.0.0"\nrequires-python = ">=3.13"\ndependencies = []\n\n'
    )
    lines[start:end] = [block]
    pyproject.write_text("".join(lines), encoding="utf-8")


def run_install(repo: Path, name: str | None = None) -> int:
    """Install dependencies and set the git hooks path; with a name, also reset and detach."""
    subprocess.run(("uv", "sync"), cwd=str(repo), check=True)
    if name is not None:
        reset_project(repo / "pyproject.toml", name)
        detach = ("git", "-C", str(repo), "remote", "remove", "origin")
        subprocess.run(detach, check=False, capture_output=True)
        sys.stderr.write(f"renamed to '{name}'; folder rename: cd .. && mv {repo.name} {name}\n")
    command = ("git", "-C", str(repo), "config", "core.hooksPath", ".githooks")
    subprocess.run(command, check=True)
    sys.stderr.write("ok: dependencies synced and git hooks path set to .githooks\n")
    return 0


def run_status(repo: Path) -> int:
    """Print the loop run registry as an aligned table."""
    registry = repo / "scratchpad" / "ralph_runs.tsv"
    if not registry.exists():
        sys.stdout.write("no runs recorded\n")
        return 0
    rows = [line.split("\t") for line in registry.read_text(encoding="utf-8").splitlines()]
    widths = [max(len(row[index]) for row in rows) for index in range(len(rows[0]))]
    for row in rows:
        sys.stdout.write("  ".join(cell.ljust(widths[index]) for index, cell in enumerate(row)) + "\n")
    return 0


def main(argv: list[str] | None = None) -> int:
    """Dispatch a ralph command."""
    args = sys.argv[1:] if argv is None else argv
    if len(args) == 1 and args[0] in GATES:
        return report(GATES[args[0]](Path.cwd()))
    if args and args[0] == "install" and len(args) <= 2:
        return run_install(Path.cwd(), args[1] if len(args) == 2 else None)
    if args == ["status"]:
        return run_status(Path.cwd())
    sys.stderr.write("usage: ralph [gate|verify|install|status]\n")
    return 2
