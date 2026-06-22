# Harness Spec

> **BACKSTOP (do not regress).** Not a build target — only touch when the gate/loop/run-records are
> broken or a new feature needs a regression test here.

## Vision

The harness is the safety backbone: a gated autonomy loop ("Ralph") that runs one bounded worker at
a time, with the filesystem as the only memory between iterations. No feature work happens until the
harness gates it. The harness must never know or care whether a worker is Claude or Codex.

## Prioritize These Items

- Keep the gate, loop, and run records working before feature changes depend on them.
- Preserve protected-path enforcement and no-bypass hook behavior.
- Keep the harness model-agnostic and filesystem-backed.

## If The Items Above Are Complete, Do These

- Add narrowly scoped regression tests for any discovered harness failure.

### Single source of truth
`specs/` says WHAT to build; `PROMPT.md` is the standing per-iteration instruction. There is no task
list, no orchestrator, and no per-task contract — each fresh worker reads the repo, picks the single
most important unfinished thing, and does it. The safety floor lives in `harness/gate.py`
(protected code), not an editable config file.

### Gate and verify
`ralph gate` (`.githooks/pre-commit`) runs fast lint + format on every commit. For the loop
(`RALPH_LOOP=1`, exported by `ralph.sh`) it also rejects any commit that touches a protected path,
adds a banned pattern (lint suppressions, hook bypasses, coverage-floor edits), or exceeds the
per-file function limit. `ralph verify` (`.githooks/pre-push` and CI) runs the heavy pass — types,
security (semgrep), tests, 100% coverage — as the real backstop.

### 100% coverage and clean lint are mandatory
Every commit must pass `ruff check`, `ruff format --check`, and `pytest` with **100% test coverage** —
the gate fails the agent otherwise. **Every single file that contains code must be at 100% coverage.**
Coverage must measure **all shipped Python**: `[tool.coverage.run] source` must include every
directory that ships runnable code, and `[tool.coverage.report]` must carry no `omit` list and no
`exclude_lines` that hide real code. New code in an unmeasured directory is a coverage hole, treated
as a gate failure to fix, not an exemption. Banned escape hatches: `# pragma: no cover`, `omit`,
lowering `--cov-fail-under` / `fail_under` (all are `forbidden_patterns`), deleting code to dodge a
test, and `xfail`/`skip` markers. There are NO xfails and NO skips on tests.

### Single-worker loop
`harness/ralph.sh [max_iterations] [max_minutes_per_iteration] <worker command...>` pipes `PROMPT.md`
on stdin to a fresh worker each iteration. It runs `uv run ralph install` first and verifies
the local gate hook is active. The loop stops at max iterations, a nonzero worker exit, or a timeout.

### Model-agnostic workers
The same loop runs Claude or Codex unchanged; the worker command is just an argument. Nothing in the
harness branches on or exposes model identity.

### Run records
Each iteration streams worker stdout/stderr to `scratchpad/runs/` and appends a row to
`scratchpad/ralph_runs.tsv` (`timestamp, iteration, pid, status, exit_code, elapsed_seconds,
stdout_path, stderr_path`), so every launch is inspectable.

## Non-goals

- Branching on model identity.
- Carrying memory between iterations through anything but the filesystem.
- Bypassing or reconfiguring git hooks.
- Letting the prompt (rather than the gate) enforce write restrictions.

## Acceptance signals

- The full check command (`ruff check`, `ruff format --check`, `pyright`, `pytest`) passes green on main.
- A commit that touches a protected path or adds a banned pattern is rejected by the gate and CI.
- The loop runs an iteration end-to-end with either a Claude or a Codex worker command, unchanged.
- Each iteration appends one well-formed row to `scratchpad/ralph_runs.tsv`.
