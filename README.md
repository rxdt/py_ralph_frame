<div align="center">
<img src="banner.svg" alt="Blue infinity loop" width="360">

<h1>L∞PS: A Python Ralph Harness</h1>
<p>No task list, no orchestrator. Just a reusable PROMPT with guards.
Loosely opinionated scaffold, easy to opt out of features, for a gated autonomous agent loop ("Ralph"). A dumb Ralph tells an agent "Go!" and hands it a PROMPT. The agent iterates on tasks from specs. Each iteration the worker commits under the pre-commit gate and updates specs; `PROMPT.md` also instructs it to push to GitHub (the harness itself does not push).</p>

![Python](https://img.shields.io/badge/Python-3.13-3776AB?logo=python&logoColor=white)
![Status](https://img.shields.io/badge/github-repo-blue?logo=github)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg?style=flat)](https://makeapullrequest.com)
![GitHub activity](https://img.shields.io/github/commit-activity/m/rxdt/py_ralph_frame)
![GitHub Release](https://img.shields.io/github/v/release/rxdt/py_ralph_frame?color=pink)
![GitHub Repo Size](https://img.shields.io/github/repo-size/rxdt/py_ralph_frame)
![X (formerly Twitter) Follow](https://img.shields.io/twitter/follow/roxdtvc)
[![](https://img.shields.io/badge/code%20style-mine-999)](https://github.com/sebmestrallet/absurd-badges)
[![](https://img.shields.io/badge/created%20an%20AGI%20by%20mistake-no-3C1)](https://github.com/sebmestrallet/absurd-badges)
![Claude](https://img.shields.io/badge/Claude-D97757?style=for-the-badge&logo=claude&logoColor=white)

</div>

---

## TLDR; Getting Started.

1. Get the scaffold: clone this repo (or use it as a GitHub template) into your project directory.
2. Set it up from inside the checkout: `uv run ralph install <your-project-name>` — renames the project, syncs dependencies, installs the git hook.
3. Write what you want to build in [docs/plan.md](docs/plan.md).
   Include statements that you _"want specs created at [specs](specs) and [docs](docs) to be updated but do NOT touch `plan.md`"_. Be specific.
4. Run the loop: `harness/ralph.sh [max_iterations] [max_minutes] <worker-agent>`
5. If agents don't get you exactly what you want, trash it, start over, and refine the plan.

---

## Details

Agents update their spec and `PROJECT_STATUS` at the end of each iteration. How things get built: the agent's `PROMPT` tells it to pick a `spec`. The `specs/` say *what* to build. The agent in the loop decides *what next*. Humans update the **MASTER** `PLAN` that refreshes `specs/`. Ideas from [ghuntley](https://github.com/ghuntley), How to Ralph Wiggum.

## Start a new project

Use with new Python projects or drop the harness and dependencies into an existing project.

1. From inside the checkout, run `uv run ralph install <your-project-name>`. Names the project, installs dependencies, and sets up the git hook.
2. Write your grand vision into `docs/plan.md`.
3. Optionally add the first spec in `specs/`, or have an agent draft the first specs.
4. Put product code under `src/` and list new source directories in `pyproject.toml [tool.coverage.run]`.
5. Strict Ruff rules, type checking, semgrep, and test coverage are set in `pyproject.toml`.
6. Your coding quirks go in `harness/preferences.py`.
7. Run a loop:

```sh
harness/ralph.sh [max_iterations] [max_minutes] <worker-agent>  # prompt-injected
```

![L∞PS Architecture Engine Flow](.loops.svg)

```sh
# For Claude, Codex, Gemini, Copilot
harness/ralph.sh 100 20 claude -p --permission-mode acceptEdits
harness/ralph.sh 10 30 codex exec --json --sandbox workspace-write -
harness/ralph.sh 2 20 gemini --yolo
harness/ralph.sh 1 10 copilot --allow-tool="shell(git:*)"
```

## A l∞p

The repo is the only memory between iterations. Each iteration is a fresh-context agent.

- `specs/` say WHAT to build
- `PROMPT.md` is the standing instruction every iteration
- `PROMPT.md` tells the agent: read `specs/`, review `src/`, build the most important unfinished thing
- agent builds
- agent commits
- every git commit passes the fast gate (lint, format, plus loop containment for the agent)
- every git push runs the full verify: types, semgrep, tests, 100% coverage
- the loop stops at `max_iterations`, a nonzero worker exit, or a timeout
- Unspecified iterations/minutes → default to 2 iterations × 20 minutes each
- Want logs? Redirect the loop: `harness/ralph.sh ... > run.log 2>&1`
- **The harness is worker-agnostic.** Any agent CLI that reads a prompt from stdin and can edit/commit works.

![L∞PS Agents](.loops_agents.svg)

- There is NO worktree/branch creation by design. Agent duties can be contained to a part of the repo. For example: Codex-1-frontend uses `specs/frontend.md`, Claude-2-researcher uses `specs/backend`...
- This choice was made:
  1. For simplicity and maintainability of the framework.
  2. Because a fresh iteration can't see unmerged work in another worktree, so agents miss context and scramble to merge while conflicts pile up.
  3. Change this behavior if you're comfortable with granting agents machine access, feeding context to agents, and managing rapidly moving git history.
  4. You can also create branches/trees and run a loop in each, then merge.
  5. If you don't like _ANYTHING_ in this framework, remove it.

## Safety

`harness/ralph.sh` launches an autonomous LLM worker with the permissions you grant it (e.g.
`--permission-mode acceptEdits`). The gate bounds what any **commit** may touch, but the worker itself is **not** sandboxed to this repo — under a permissive mode it can run arbitrary shell. You are authorizing real changes. Choose the worker and permission mode deliberately. Use `git log --oneline <branch>..HEAD` to show what's unpushed.

#### The Gate: Tiered Checks

The safety minimum is in code: `harness/gate.py` holds `FORBIDDEN_PATHS` and `FORBIDDEN_PATTERNS`; `semgrep` comes from `pyproject.toml`; `harness/preferences.py` holds the style checks other tools can't catch, e.g. `MAX_FUNCTIONS_PER_FILE`. Containment runs when `RALPH_LOOP=1`, which `ralph.sh` sets at each invocation. Humans commit normally while agents in the loop get stronger checks.

⚡ `uv run ralph gate` (pre-commit) → fast checks.
Ruff lint + check format for everyone, _plus_ **containment** for the agents (via `RALPH_LOOP=1` set by `ralph.sh`): `FORBIDDEN_PATHS` + `FORBIDDEN_PATTERNS` + preferences, including `MAX_FUNCTIONS_PER_FILE`.

✅ `uv run ralph verify` (pre-push) → the heavy quality pass: ruff lint + check format, pyright, pylint, semgrep, pytest @ 100% cov — no containment re-check. CI re-runs these quality checks on every PR and every push to `<branch>` as the backstop.

Humans can use normal `git` commands.

Forbidden agent paths — `AGENTS.md`, `harness/`, `tests/harness/`, `.githooks/`, `.github/`,
`pyproject.toml`. Humans own them (`harness/preferences.py` is part of `harness/`).

## Layout

```
harness/        the gate, loop (ralph.sh), CLI, custom user checks   (forbidden)
tests/harness/  the harness's own tests                              (forbidden)
.githooks/      pre-commit / pre-push gate hooks                     (forbidden)
.github/        CI that re-runs the gate                             (forbidden)
pyproject.toml  project + tooling config                             (forbidden)
AGENTS.md       rules for agents working in the repo                 (forbidden)
PROMPT.md       the standing per-iteration instruction
specs/          WHAT to build, one PRIORITY-bannered file per track
src/            your product/source code (add to coverage source)
docs/           PLAN; PROJECT_STATUS
scratchpad/     scratch dir agents are pointed at for temp files
```

## ⚠️ Warnings. Read this before a first run.

1. **The gate is a guardrail, not a jail.** Agents are smart and crafty — like people. They will find a way to complete a task at all costs. Lock the worker down with its own settings (permissions and sandbox flags), add branch protection and required CI, and **trust nothing and no one.**

2. **This harness does not sandbox your machine.** It *tries* to contain the loop — the gate limits which paths a commit may touch, bans escape-hatch patterns, and steers writes into repo `scratchpad/`. But a worker can still run arbitrary shell commands. For real isolation, constrain all agents from a higher level, use permission/deny rules, or run everything in a container.

3. **Mind your usage limits.** `ralph.sh` works to a cap. If you set caps high, or run several workers from the same provider at once, you will burn through your tokens, context windows, and provider usage limits. **Workers keep working as long as there is work to do.** There is always work to do. Recall defaults: **2 loops x 20 minutes**.

4. **`PROMPT.md` tells the worker to push every iteration** (the harness itself does not push or verify commits), so autonomous commits reach the remote continuously. **If you want to protect `main`, run the loop on its own branch and merge via PR/CI** — a protected `main` rejects the push and stalls the loop.

5. **100% coverage does not mean good tests.** That is quantity, not quality. If you had the same agents that wrote the code write the tests "green" can mean nothing. Tests should challenge source.

6. Suggestions. `chmod 700 ralph.sh` to limit read/run for the script. `chmod 600 pyproject.toml` once it is set how you want. Agents acting as you will not be limited by this but it will stall them and if the file changes you will know why.

## Commands

```sh
uv run ralph install <your-project-name>  # uv sync + set hooks path; with a name, also rewrites the [project] name
uv run ralph gate  # fast checks: ruff lint + format (plus agent containment)
uv run ralph verify  # full pass: ruff, format, pyright, pylint, semgrep, pytest @ 100% cov
uv run ralph status  # recent logs

git config --get core.hooksPath .githooks  # must print `.githooks` (blank = gate never runs)
ls -la .githooks/pre-commit   # must exist to be executable
-rwxr-xr-x@ 1 owner  staff  161 Jun 23 00:06 .githooks/pre-commit

# anything else → prints usage:
ralph [gate|verify|install [name]|status] (exit 2)
# Underlying tools the gate calls
ruff check .
ruff format  # to fix add .
pyright
pylint harness src
semgrep scan --config auto --config p/secrets --error --quiet .
pytest
# Note: Pydantic is included. Use it.
```

## For agents

· Rules: `AGENTS.md` · What to build: `specs/` · Standing instruction: `PROMPT.md` ·

Use your best judgment · Leave the code how you would like to find it ·

Human and agent-owned status interface: `docs/PROJECT_STATUS.md`.
