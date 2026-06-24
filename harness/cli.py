"""Command-line interface for the ralph harness."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import tomlkit
import typer
from packaging.utils import InvalidName, canonicalize_name

from harness.gate import run_gate, run_verify

app = typer.Typer(name="ralph", help="ralph harness commands", no_args_is_help=True)


@app.command(help="report the most recent agent run logs (scratchpad/runs/*.jsonl); RUNS defaults to 10")
def status(runs: int = typer.Argument(10)) -> None:
    """Summarize recent agent JSON receipts: event count + ok/error reason per run."""
    typer.echo("# agent logs (scratchpad/runs)")
    logs = sorted((Path.cwd() / "scratchpad" / "runs").glob("*.jsonl"))
    if not logs:
        typer.echo("(none)")
        return

    for path in logs[-runs:]:
        count = 0
        reason = ""
        for line in path.read_text(encoding="utf-8").splitlines():
            count += 1
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(obj, dict):
                continue
            error = obj.get("error")
            if obj.get("type") == "error" or obj.get("is_error") or error:
                detail = error.get("message") if isinstance(error, dict) else error
                reason = detail or obj.get("message") or obj.get("subtype") or "error"

        status_text = f"error: {reason}" if reason else "ok"
        typer.echo(f"{path.name}: {count} events, {status_text}")


@app.command(help="Quick run of lint, format check, pyright, semgrep, pytest + agent containment")
def gate() -> None:
    """Run the fast pre-commit gate (lint/format, plus loop containment)."""
    problems = run_gate(Path.cwd())
    for problem in problems:
        typer.echo(f"gate: {problem}", err=True)
    typer.echo("rejected by ralph" if problems else "ok: gate passed", err=True)
    raise typer.Exit(code=1 if problems else 0)


@app.command(help="run the full pre-push verification")
def verify() -> None:
    """Run the full pre-push verification (types, security, tests, coverage)."""
    problems = run_verify(Path.cwd())
    for problem in problems:
        typer.echo(f"gate: {problem}", err=True)
    typer.echo("rejected by ralph" if problems else "ok: pre-push verify passed", err=True)
    raise typer.Exit(code=1 if problems else 0)


@app.command(help="Setup a new project")
def install(name: str | None = typer.Argument(None)) -> None:
    """Sync deps and activate the gate hook; optionally rename the project first.

    A name is normalized to the PEP 503/508 form via ``packaging``. The TOML is round-tripped
    through ``tomlkit`` to keep the file's existing formatting and comments.
    """
    repo = Path.cwd()
    if name:
        try:
            normalized = canonicalize_name(name, validate=True)
        except InvalidName as error:
            typer.echo(f"ralph: {error}", err=True)
            raise typer.Exit(code=2) from error
        pyproject = repo / "pyproject.toml"
        document = tomlkit.parse(pyproject.read_text(encoding="utf-8"))
        document.setdefault("project", tomlkit.table())["name"] = normalized
        pyproject.write_text(tomlkit.dumps(document), encoding="utf-8")
    subprocess.run(("uv", "sync"), cwd=str(repo), check=True)
    subprocess.run(("git", "-C", str(repo), "config", "core.hooksPath", ".githooks"), check=True)

    typer.echo("ok: dependencies synced and git hooks path set to .githooks", err=True)


def main(argv: list[str] | None = None) -> int:
    """Console-script entry point (`ralph`); return the process exit code."""
    try:
        app(args=argv)
    except SystemExit as exit_error:
        return exit_error.code if isinstance(exit_error.code, int) else 1
    return 0
