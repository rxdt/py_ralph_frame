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


def set_project_name(pyproject: Path, name: str) -> None:
    """Rename the project in-place: rewrite the `name =` line under [project]."""
    lines = pyproject.read_text(encoding="utf-8").splitlines(keepends=True)
    start = next(index for index, line in enumerate(lines) if line.startswith("[project]"))
    target = next(index for index in range(start + 1, len(lines)) if lines[index].startswith("name ="))
    lines[target] = f'name = "{name}"\n'
    pyproject.write_text("".join(lines), encoding="utf-8")


def initialize_project(repo: Path) -> int:
    """Install dependencies and point git at the tracked hooks directory."""
    subprocess.run(("uv", "sync"), cwd=str(repo), check=True)
    command = ("git", "-C", str(repo), "config", "core.hooksPath", ".githooks")
    subprocess.run(command, check=True)
    sys.stderr.write("ok: dependencies synced and git hooks path set to .githooks\n")
    return 0


def run_install(repo: Path, name: str | None = None) -> int:
    """Set up the current repo: optionally rename the project, then sync deps and set hooks."""
    if name is not None:
        set_project_name(repo / "pyproject.toml", name)
    return initialize_project(repo)


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
        result = report(GATES[args[0]](Path.cwd()))
    elif args and args[0] == "install" and len(args) <= 2:
        result = run_install(Path.cwd(), args[1] if len(args) == 2 else None)
    elif args == ["status"]:
        result = run_status(Path.cwd())
    else:
        sys.stderr.write("usage: ralph [gate|verify|install [name]|status]\n")
        result = 2
    return result
