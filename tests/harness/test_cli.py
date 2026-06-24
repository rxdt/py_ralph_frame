"""Tests for the ralph command-line interface."""

from __future__ import annotations

import subprocess
import sys
from typing import TYPE_CHECKING

import pytest
from conftest import run_cmd

from harness import cli

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path


def passthrough_skip_uv(real: Callable[..., object], calls: list[tuple[str, ...]]) -> Callable[..., object]:
    """Record every command and run it for real, but stub out the slow `uv sync`."""

    def runner(
        args: tuple[str, ...],
        check: bool = False,
        capture: bool = False,
        cwd: str | None = None,
    ) -> object:
        calls.append(tuple(args))
        if tuple(args[:2]) == ("uv", "sync"):
            return subprocess.CompletedProcess(list(args), 0)
        return real(args, check=check, capture_output=capture, cwd=cwd)

    return runner


def fake_gate_clean(repo: Path) -> list[str]:
    """Report a clean gate without running anything."""
    del repo
    return []


def fake_gate_problems(repo: Path) -> list[str]:
    """Report one gate violation without running anything."""
    del repo
    return ["forbidden path modified: harness/x.py"]


def test_gate_command_clean(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """A clean gate exits 0."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli, "run_gate", fake_gate_clean)
    assert cli.main(["gate"]) == 0


def test_gate_command_problems(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Gate violations exit 1."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli, "run_gate", fake_gate_problems)
    assert cli.main(["gate"]) == 1


def test_verify_command_problems(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """The verify command reports violations and exits 1."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli, "run_verify", fake_gate_problems)
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


def test_install_activates_inactive_gate_hook(monkeypatch: pytest.MonkeyPatch, git_repo: Path) -> None:
    """A fresh repo has no hooks path (gate inactive); install activates the tracked gate hook."""
    monkeypatch.chdir(git_repo)
    before = subprocess.run(
        ["git", "config", "--get", "core.hooksPath"],
        cwd=git_repo,
        capture_output=True,
        text=True,
        check=False,
    )
    assert before.returncode != 0  # unset == the gate hook is not active before install
    monkeypatch.setattr(cli.subprocess, "run", passthrough_skip_uv(subprocess.run, []))
    assert cli.main(["install"]) == 0
    monkeypatch.undo()
    assert run_cmd(["git", "config", "core.hooksPath"], git_repo).strip() == ".githooks"


def test_install_name_renames_project_in_place(monkeypatch: pytest.MonkeyPatch, git_repo: Path) -> None:
    """install <name> rewrites the project name in the current pyproject, keeping [project.scripts]."""
    monkeypatch.chdir(git_repo)
    (git_repo / "pyproject.toml").write_text(
        '[project]\nname = "ralph-harness"\nversion = "0.1.0"\n\n'
        '[project.scripts]\nralph = "harness.cli:main"\n',
        encoding="utf-8",
    )
    calls: list[tuple[str, ...]] = []
    monkeypatch.setattr(cli.subprocess, "run", passthrough_skip_uv(subprocess.run, calls))
    assert cli.main(["install", "myproj"]) == 0
    assert ("uv", "sync") in calls
    monkeypatch.undo()
    text = (git_repo / "pyproject.toml").read_text(encoding="utf-8")
    assert 'name = "myproj"' in text
    assert 'ralph = "harness.cli:main"' in text
    out = run_cmd(["git", "config", "core.hooksPath"], git_repo)
    assert out.strip() == ".githooks"


def test_install_rejects_invalid_name_before_writes(monkeypatch: pytest.MonkeyPatch, git_repo: Path) -> None:
    """A name that could corrupt pyproject.toml is refused before file or subprocess writes."""
    monkeypatch.chdir(git_repo)
    pyproject = git_repo / "pyproject.toml"
    original = '[project]\nname = "ok"\n'
    pyproject.write_text(original, encoding="utf-8")
    calls: list[tuple[str, ...]] = []
    monkeypatch.setattr(cli.subprocess, "run", passthrough_skip_uv(subprocess.run, calls))
    assert cli.main(["install", 'bad"name']) == 2
    assert pyproject.read_text(encoding="utf-8") == original
    assert calls == []


def test_install_invalid_name_is_clean_cli_error(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """`ralph install <bad>` exits 2 with a message instead of a raw ValueError traceback."""
    monkeypatch.chdir(tmp_path)
    assert cli.main(["install", 'bad"name']) == 2


def write_receipt(git_repo: Path, name: str, body: str) -> None:
    """Drop an agent JSON receipt under scratchpad/runs."""
    runs = git_repo / "scratchpad" / "runs"
    runs.mkdir(parents=True, exist_ok=True)
    (runs / name).write_text(body, encoding="utf-8")


def test_status_summarizes_agent_logs_with_error(
    monkeypatch: pytest.MonkeyPatch, git_repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """status surfaces the failure reason from an agent's `error` event so users know why a run died."""
    monkeypatch.chdir(git_repo)
    write_receipt(
        git_repo,
        "20260101T000000Z-claude.jsonl",
        '{"type":"system"}\n{"type":"error","error":{"message":"rate limit exceeded"}}\n',
    )
    assert cli.main(["status"]) == 0
    out = capsys.readouterr().out
    assert "# agent logs (scratchpad/runs)" in out
    assert "20260101T000000Z-claude.jsonl: 2 events, error: rate limit exceeded" in out


def test_status_logs_ok_and_tolerates_partial_lines(
    monkeypatch: pytest.MonkeyPatch, git_repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A receipt with no error reads `ok`; a non-JSON partial line is counted but does not crash."""
    monkeypatch.chdir(git_repo)
    write_receipt(git_repo, "20260101T000001Z-codex.jsonl", 'not json yet\n{"type":"item.completed"}\n')
    assert cli.main(["status"]) == 0
    assert "20260101T000001Z-codex.jsonl: 2 events, ok" in capsys.readouterr().out


def test_status_logs_none_when_empty(
    monkeypatch: pytest.MonkeyPatch, git_repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """With no logs on disk the section reports `(none)` rather than failing."""
    monkeypatch.chdir(git_repo)
    assert cli.main(["status"]) == 0
    assert "# agent logs (scratchpad/runs)\n(none)" in capsys.readouterr().out


def test_status_limits_agent_logs_to_most_recent_runs(
    monkeypatch: pytest.MonkeyPatch, git_repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The RUNS argument keeps old receipts out of status output."""
    monkeypatch.chdir(git_repo)
    write_receipt(git_repo, "20260101T000000Z-old.jsonl", '{"type":"old"}\n')
    write_receipt(git_repo, "20260101T000001Z-newer.jsonl", '{"type":"newer"}\n')
    write_receipt(git_repo, "20260101T000002Z-newest.jsonl", '{"type":"newest"}\n')
    assert cli.main(["status", "2"]) == 0
    out = capsys.readouterr().out
    assert "20260101T000000Z-old.jsonl" not in out
    assert "20260101T000001Z-newer.jsonl: 1 events, ok" in out
    assert "20260101T000002Z-newest.jsonl: 1 events, ok" in out


def test_status_reads_error_given_as_string(
    monkeypatch: pytest.MonkeyPatch, git_repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """An `error` value that is a bare string (not an object) is surfaced verbatim."""
    monkeypatch.chdir(git_repo)
    write_receipt(git_repo, "20260101T000100Z-codex.jsonl", '{"type":"error","error":"disk full"}\n')
    assert cli.main(["status"]) == 0
    assert "20260101T000100Z-codex.jsonl: 1 events, error: disk full" in capsys.readouterr().out


def test_status_uses_is_error_flag_and_message_fallback(
    monkeypatch: pytest.MonkeyPatch, git_repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`is_error` with no `error` object falls back to the event's top-level `message`."""
    monkeypatch.chdir(git_repo)
    write_receipt(git_repo, "20260101T000200Z-claude.jsonl", '{"is_error":true,"message":"killed"}\n')
    assert cli.main(["status"]) == 0
    assert "20260101T000200Z-claude.jsonl: 1 events, error: killed" in capsys.readouterr().out


def test_status_falls_back_to_subtype_then_generic(
    monkeypatch: pytest.MonkeyPatch, git_repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Reason resolves to `subtype` when present, else the generic 'error'."""
    monkeypatch.chdir(git_repo)
    write_receipt(git_repo, "20260101T000300Z-a.jsonl", '{"type":"error","subtype":"timeout"}\n')
    write_receipt(git_repo, "20260101T000301Z-b.jsonl", '{"type":"error"}\n')
    assert cli.main(["status"]) == 0
    out = capsys.readouterr().out
    assert "20260101T000300Z-a.jsonl: 1 events, error: timeout" in out
    assert "20260101T000301Z-b.jsonl: 1 events, error: error" in out


def test_status_counts_non_dict_json_as_event(
    monkeypatch: pytest.MonkeyPatch, git_repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A valid-JSON line that is not an object (a bare number) counts but cannot be an error."""
    monkeypatch.chdir(git_repo)
    write_receipt(git_repo, "20260101T000400Z-codex.jsonl", "42\n")
    assert cli.main(["status"]) == 0
    assert "20260101T000400Z-codex.jsonl: 1 events, ok" in capsys.readouterr().out


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


def test_main_maps_non_int_exit_code_to_one(monkeypatch: pytest.MonkeyPatch) -> None:
    """A SystemExit carrying a non-int code (e.g. a message) is reported as exit 1."""

    def exit_with_message(args: list[str] | None = None) -> None:
        del args
        message = "boom"
        raise SystemExit(message)

    monkeypatch.setattr(cli, "app", exit_with_message)
    assert cli.main([]) == 1


def test_main_returns_zero_when_app_does_not_exit(monkeypatch: pytest.MonkeyPatch) -> None:
    """If the app returns without raising SystemExit, main reports success."""

    def quiet(args: list[str] | None = None) -> None:
        del args

    monkeypatch.setattr(cli, "app", quiet)
    assert cli.main([]) == 0
