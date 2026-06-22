# Project Status

> Current truth of the repo. HUMAN-ONLY (protected). Each iteration may *read* this; only a human
> edits it. Keep it short and current — it is the first thing a fresh worker should trust.

## Now

- Fresh scaffold. Harness + gate + loop in place; no product code yet.

## Checks

- `uv run ruff check . && uv run ruff format --check . && uv run pyright && uv run pytest` — green.

## Next

- Write the first real spec in `specs/`, then run the loop.

## Blockers

- None.
