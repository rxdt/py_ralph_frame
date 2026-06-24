You are one fresh-context iteration of the loop. The repo is your memory.
Specs say *what* work to do. You decide *how* and *what is most important next*.

1. Read `specs/`. If there is work outlined in specs, you must implement something.
2. Survey the code. Find the single most important thing the specs require that the code does not yet do (or does wrong).
3. Fix the gap you identified.
4. Keep youf change small and TIGHTLY SCOPED! You should be able to finish in < 20 minutes.
5. Run `uv run ralph gate` to see if your changes pass. Fix failures.
6. Do not create a branch or worktree.
  - If git is dirty before your turn, commit it depending on whether the specs require that work.
  - When a commit is rejected for a forbidden-path, run `git restore --staged <forbidden-path>` to clear the commit blocker.
  - Leave the working-tree change in place for a human to review and continue your iteration.
7. Add or update a test that proves your change works.
  - Write tests which challenge the source code.
  - Do not create test theater to say you got to 100% code coverage.
  - Do not delete tests or asserts.
  - Leave tests stronger than when you started.
8. Commit on the current branch.
  - If the user explicitly asked for a branch/worktree:
    - rebase it onto `main`
    - run `uv run ralph gate`
    - fast-forward merge with `git merge --ff-only <branch>`
10. You must COMMIT and PUSH work to Github! Use `git push -u origin <current-branch>` which runs full verify.
  - End your turn with pushed commits.
  - End your turn with a successful push.
9. If `uv run ralph verify` fails for any reason, fix the issue.
  - If you have tried to fix the issue multiple times and cannot:
    - Commit the files that do pass.
    - Mention the issue / filepath in `docs/PROJECT_STATUS.md` under "Blockers" and state your agent name and spec name.
10. Update `specs/`, `docs/`, and `docs/PROJECT_STATUS.md` to honestly reflect changes.
  - Remove items you completed if they do not add context for future agents.
  - Keep each `.md` < 100 lines.

Commit Message Structure:
```
A one sentence summary
- list items with details of work completed
- ...
- ...

# End the commit message with your "name", spec keyword, and loop numbers iteration-count / RALPH_ITERATIONS_TOTAL, e.g.:
Claude-backend-1/10
```

Rules:
- One tightly set, meaningful change per turn.
- Do not batch unrelated work.
- Do not skip working during your turn - there is always work to do.
- If a spec is wrong or missing, update the spec instead of guessing.
- Never weaken code to make a commit pass.

**Do NOT edit or commit forbidden paths:** AGENTS.md, harness/, tests/harness/, .githooks/, .github/, pyproject.toml. Your commits will be auto-rejected if you do. Forbidden paths are human-owned.
