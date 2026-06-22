"""Tests for the Ralph loop script."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
RALPH = REPO_ROOT / "harness" / "ralph.sh"
HEADER = "timestamp\titeration\tpid\tstatus\texit_code\telapsed_seconds\tstdout_path\tstderr_path"


def write_executable(path: Path, text: str) -> None:
    """Write an executable test helper script."""
    path.write_text(text, encoding="utf-8")
    path.chmod(0o755)


def fake_uv(path: Path) -> None:
    """Create a fake uv whose only job is to mark the gate hook installed."""
    write_executable(
        path,
        """#!/bin/sh
if [ "$1" = "run" ] && [ "$2" = "ralph" ] && [ "$3" = "install" ]; then
    touch .fake-installed-hook
    exit 0
fi
exit 9
""",
    )


def fake_timeout(path: Path) -> None:
    """Create a fake timeout command that delegates to the worker."""
    write_executable(path, '#!/bin/sh\nshift\nexec "$@"\n')


def fake_git(path: Path) -> None:
    """Create a fake git that reports the hook path once install ran."""
    write_executable(
        path,
        """#!/bin/sh
if [ "$1" = "config" ] && [ "$2" = "--get" ]; then
    if [ -n "${FAKE_HOOK_PATH:-}" ]; then
        printf '%s\\n' "$FAKE_HOOK_PATH"
        exit 0
    fi
    [ -f .fake-installed-hook ] && printf '.githooks\\n'
    exit 0
fi
exit 0
""",
    )


def run_ralph(
    tmp_path: Path,
    worker: Path,
    ralph_args: list[str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run Ralph in a temp repo with fake uv, timeout, and git commands."""
    (tmp_path / "PROMPT.md").write_text("do the most important thing\n", encoding="utf-8")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    fake_uv(bin_dir / "uv")
    fake_timeout(bin_dir / "timeout")
    fake_git(bin_dir / "git")
    env = os.environ.copy()
    env["PATH"] = f"{bin_dir}{os.pathsep}{env['PATH']}"
    command = [str(RALPH)]
    command.extend(ralph_args or [])
    command.append(str(worker))
    return subprocess.run(command, cwd=tmp_path, capture_output=True, text=True, check=False, env=env)


def registry_rows(tmp_path: Path) -> list[str]:
    """Return the Ralph registry lines."""
    return (tmp_path / "scratchpad" / "ralph_runs.tsv").read_text(encoding="utf-8").splitlines()


def test_usage_fails_when_agent_command_is_missing(tmp_path: Path) -> None:
    """The worker command is required."""
    result = subprocess.run([str(RALPH)], cwd=tmp_path, capture_output=True, text=True, check=False)
    assert result.returncode == 2
    assert "[max_iterations]" in result.stderr
    assert "defaults: max_iterations=2" in result.stderr


def test_missing_timeout_binary_fails_clearly(tmp_path: Path) -> None:
    """Ralph fails before work when no timeout command is available."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    fake_uv(bin_dir / "uv")
    result = subprocess.run(
        [str(RALPH), "worker"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
        env={"PATH": str(bin_dir)},
    )
    assert result.returncode == 2
    assert "install gtimeout or timeout" in result.stderr


def test_hook_installed_and_loop_records_runs(tmp_path: Path) -> None:
    """Ralph installs the gate hook, then loops and records each run."""
    worker = tmp_path / "worker.sh"
    write_executable(worker, "#!/bin/sh\ncat > received-prompt.txt\nexit 0\n")
    result = run_ralph(tmp_path, worker, ["1", "1"])
    assert result.returncode == 0
    assert (tmp_path / ".fake-installed-hook").is_file()
    assert (tmp_path / "received-prompt.txt").read_text(encoding="utf-8") == (
        "do the most important thing\n\nRALPH_ITERATION=1/1\n"
    )
    rows = registry_rows(tmp_path)
    assert rows[0] == HEADER
    cells = rows[1].split("\t")
    assert cells[1:5] == ["1", cells[2], "exited", "0"]


def test_hook_not_active_aborts_before_work(tmp_path: Path) -> None:
    """Ralph stops if the gate hook is still off after install."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    write_executable(
        bin_dir / "uv",
        """#!/bin/sh
[ "$3" = "install" ] && exit 0
exit 9
""",
    )
    fake_timeout(bin_dir / "timeout")
    fake_git(bin_dir / "git")
    (tmp_path / "PROMPT.md").write_text("x\n", encoding="utf-8")
    env = os.environ.copy()
    env["PATH"] = f"{bin_dir}{os.pathsep}{env['PATH']}"
    result = subprocess.run(
        [str(RALPH), "true"], cwd=tmp_path, capture_output=True, text=True, check=False, env=env
    )
    assert result.returncode == 2
    assert "local gate hook is not active after install" in result.stderr


def test_default_iterations_are_two_when_omitted(tmp_path: Path) -> None:
    """Omitting max_iterations runs up to the default of two loops."""
    worker = tmp_path / "worker.sh"
    write_executable(worker, "#!/bin/sh\nexit 0\n")
    result = run_ralph(tmp_path, worker, [])
    assert result.returncode == 0
    rows = registry_rows(tmp_path)
    assert len(rows) == 3
    assert "iteration 1/2" in result.stderr
    assert "iteration 2/2" in result.stderr
    assert "All worker commands exited 0, which means success" in result.stderr
    assert "verify git status, commits, pushes, and merges separately" in result.stderr


def test_nonzero_worker_exit_is_recorded_and_stops(tmp_path: Path) -> None:
    """A worker abort is recorded and stops Ralph immediately."""
    worker = tmp_path / "worker.sh"
    write_executable(worker, "#!/bin/sh\nexit 7\n")
    result = run_ralph(tmp_path, worker, ["2", "1"])
    assert result.returncode == 1
    rows = registry_rows(tmp_path)
    assert len(rows) == 2
    assert rows[1].split("\t")[3:5] == ["failed", "7"]
    assert "worker exited with status 7; stopping" in result.stderr


def test_timeout_is_recorded_and_stops(tmp_path: Path) -> None:
    """Timeout status is recorded and Ralph stops immediately."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    fake_uv(bin_dir / "uv")
    fake_git(bin_dir / "git")
    write_executable(bin_dir / "gtimeout", "#!/bin/sh\nexit 124\n")
    write_executable(bin_dir / "timeout", "#!/bin/sh\nexit 124\n")
    worker = tmp_path / "worker.sh"
    write_executable(worker, "#!/bin/sh\nexit 0\n")
    (tmp_path / "PROMPT.md").write_text("x\n", encoding="utf-8")
    env = os.environ.copy()
    env["PATH"] = f"{bin_dir}{os.pathsep}{env['PATH']}"
    env["FAKE_HOOK_PATH"] = ".githooks"
    result = subprocess.run(
        [str(RALPH), "2", "1", str(worker)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    assert result.returncode == 1
    rows = registry_rows(tmp_path)
    assert len(rows) == 2
    assert rows[1].split("\t")[3:5] == ["timeout", "124"]


def test_gtimeout_is_preferred(tmp_path: Path) -> None:
    """Ralph prefers gtimeout when both timeout commands exist."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    fake_uv(bin_dir / "uv")
    fake_timeout(bin_dir / "timeout")
    fake_git(bin_dir / "git")
    write_executable(
        bin_dir / "gtimeout",
        "#!/bin/sh\nprintf 'gtimeout\\n' > used-timeout\nshift\nexec \"$@\"\n",
    )
    worker = tmp_path / "worker.sh"
    write_executable(worker, "#!/bin/sh\nexit 0\n")
    (tmp_path / "PROMPT.md").write_text("x\n", encoding="utf-8")
    env = os.environ.copy()
    env["PATH"] = f"{bin_dir}{os.pathsep}{env['PATH']}"
    env["FAKE_HOOK_PATH"] = ".githooks"
    subprocess.run(
        [str(RALPH), "1", "1", str(worker)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    assert (tmp_path / "used-timeout").read_text(encoding="utf-8") == "gtimeout\n"


def test_script_has_no_bashisms() -> None:
    """The shell script parses as POSIX sh."""
    assert shutil.which("sh") is not None
    result = subprocess.run(["sh", "-n", str(RALPH)], capture_output=True, text=True, check=False)
    assert result.returncode == 0
