# Project Status

> Current truth of the repo. Keep it short and current. Human-agent interface point.

## Now

- The active spec now describes the Ralph harness instead of template placeholders.
- Dirty human-owned guardrail files existed before this iteration and were left untouched.

## Checks

- `uv run ralph preflight` — failed before checks: `ralph` executable not found.
- `uv run python -m harness.cli preflight` — passed.
- `uv run pytest tests/test_specs.py` — passed.

## Next

- Run the loop from `specs/base.md`.
- Add downstream product code only after the human plan names a concrete project.

## Blockers
- `docs/plan.md` was rejected by the commit hook as forbidden; its working-tree edit is left unstaged for human review.
- Pre-existing dirty forbidden files may block agent containment or commit hooks; Codex-base-1/1 left them untouched.
