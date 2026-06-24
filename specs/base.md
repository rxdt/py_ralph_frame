# Base Spec

> **PRIORITY 1 (active).** Keep the reusable Ralph harness ready for fresh-context loop iterations.

## Vision

This repository is a Python Ralph harness scaffold. A fresh agent should be able to pick an active spec, make one bounded change, and leave the repo resumable without touching human-owned guardrail files.

## Prioritize These Items

- Replace the template spec with concrete Ralph harness direction.
- Add a test that fails if the active spec regresses into a template.

## If The Items Above Are Complete, Do These

- Add product code only after the human plan names a concrete downstream project.
- Keep harness behavior changes out of agent-owned iterations unless a human assigns them.

## Acceptance Signals

- `specs/base.md` has an active priority banner and no template markers.
- A non-harness test protects the active spec from template regression.

## Non-goals

- Changing `harness/`, `tests/harness/`, `.githooks/`, `.github/`, `pyproject.toml`, or `AGENTS.md`.
- Inventing downstream product behavior before the plan asks for it.
