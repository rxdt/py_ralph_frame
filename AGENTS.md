# FUNCTIONALITY

## Repository boundary

- Work only inside this repository; use `scratchpad/` for temporary files.
- Do not read, write, or search outside the repo unless the user explicitly asks.
- Do not edit protected paths: `AGENTS.md`, `harness/` (except `harness/preferences.py`), `tests/harness/`, `.githooks/`, `.github/`, `pyproject.toml`. The gate enforces this; the list lives in `harness/gate.py`. You may edit `harness/preferences.py` — it is the tunable style-knobs file.

## The loop

- `PROMPT.md` is the standing per-iteration instruction.
- `specs/` says WHAT to build; with a PRIORITY banner at the top.
- Read `specs/`, pick the single most important unfinished item: scope it, implement it, commit often. Update the spec to the truth. One tightly scoped change per iteration.

## Safety floor

- The floor is code in `harness/gate.py` (protected). Leave it unchallenged.
- Strengthen tests and coverage. Pass lint, type, and gate checks.
- Avoid lint suppressions, type-ignores, skipped/xfail tests, or broad exception swallowing.
- Never run destructive git commands (`rm -rf`, `git reset --hard`, `git branch -D`) unless the user  explicitly asks; verify each risky step.
- Never bypass or reconfigure git hooks.

## Commit and verify

- `ralph gate` runs on commit — fast lint + format, plus loop containment.
- Run `uv run ralph verify` often, especially before pushing: lint, format, types, security, tests, 100% coverage.
- Done means: no protected path touched; `ralph verify` is green; the spec and `docs/PROJECT_STATUS.md` reflect what was built; tests pass, cover the change, and honestly challenge the source code.

## Documentation

- Every `.md` stays under 100 lines — distill for the next agent.
- Keep the doc set small: README, AGENTS, `docs/PLAN`, `docs/PROJECT_STATUS`, `specs/`, `PROMPT.md`.

## Session handoff

- At <=40% of your context window, stop expanding scope.
    - Update `docs/PROJECT_STATUS.md` with new state, checks, commit/branch, blockers, and next steps.
    - Update your spec.
    - Leave the repo resumable.
    - Commit through the gate, push, then merge when safe.

# RULES

## 1. Think First

**Verify assumptions. Surface confusion. Note tradeoffs.**

Before implementing:
- State assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Request clarity.
- Review source code and tests.

## 2. Simplicity

**Only the minimum code that solves the problem**

- Strict scope compliance.
- Readable and reusable code.
- Prune code written for unlikely error paths.
- Avoid sprawl. 200 lines could be 50: rewrite.
- Be clear, not clever.

Ask: "Would a human say this is over-engineered?" Then simplify.

## 3. Surgical Edits

**Touch minimal surfaces. Clean up only your own mess.**

- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that weren't assigned to you.
- If you notice unrelated dead code, mention it - don't delete it.
- Remove imports/variables/functions that YOUR changes orphaned.

Acceptance criteria: Each changed line traces directly to the user's request.

## 4. Python

- Write simple, readable, fully typed Python.
- Prefer module-level functions over classes; use a dataclass for grouped data or behavior.
- Avoid AI-bloat like:
  - wrapping literals in their constructors (`"x"`, not `str("x")`; `[]`, not `list([])`)
  - repeated string normalization (`.lower()`/`.strip()`/`.replace()`)
  - overly defensive checks
