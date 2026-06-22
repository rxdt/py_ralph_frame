# Ralph loop prompt

You are one fresh-context iteration of the loop. The repo is your memory.

1. Read `specs/` — that is what we must build
2. First run the gate: `uv run ruff check . && uv run ruff format --check . && uv run pytest`. If it is red (lint, format, tests, or <100% coverage on any file with code), fixing it IS the single most important thing — do that this iteration before anything else.
3. Otherwise, survey the code. Find the single most important thing the specs require that the code does not yet do (or does wrong).
4. Do exactly that one thing. Keep the change small.
5. Work in the current checkout. Do not create a worktree unless the user explicitly asked for one.
   If `git status --short` is dirty before your own edits, stop and report the dirty paths instead
   of hiding work on another branch.
6. Ensure tests and lint pass. Add or update a test that proves your change works. Write tests which challenge the source code.
7. Commit directly on the current branch through the normal git hook. Do not call nonexistent
   integration helpers. If the user explicitly asked for a branch/worktree, rebase it onto `main`,
   run the full gate there, then fast-forward merge with `git merge --ff-only <branch>`.
8. Push to GitHub every iteration. After committing, run `git push` to publish this iteration's
   commit to the remote (use `git push -u origin <branch>` on a new branch). The pre-push hook runs
   the full verify; a green push saves your work on GitHub. Never end an iteration with unpushed commits.

Rules:
- One meaningful change per iteration. Do not batch unrelated work.
- Specs say *what*. You decide *how* and *what is most important next*.
- If a spec is wrong or missing, update the spec instead of guessing.
- Never weaken the gate, tests, or coverage to make a commit pass.

Commit Message:
```
1 sentence summary

- list items with details of work completed
- ...

End the commit message with your worker name, spec keyword, and `RALPH_ITERATION`, e.g. `Claude-backend-1/10`.
```
