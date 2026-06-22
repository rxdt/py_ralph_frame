#!/bin/sh
# Ralph loop: run a fresh-context agent against PROMPT.md every iteration.
# The repo is the only memory between iterations. PROMPT.md tells the agent to
# read specs/, pick the single most important unfinished thing, do it, and
# commit under the gate. There is no task list and no orchestrator.
#
# Usage:
#   harness/ralph.sh [max_iterations] [max_minutes_per_iteration] <agent command...>
#  e.g.
#   harness/ralph.sh claude -p --permission-mode acceptEdits
#   harness/ralph.sh 50 20 codex exec --json --sandbox workspace-write -
#
# ****      Motto: Keep Ralph Dumb.      ****
#
# PROMPT.md is piped to the worker's stdin. Worker stdout/stderr stream to
# scratchpad/runs/ so each launch is inspectable. The loop stops at max
# iterations, a nonzero worker exit, or a timeout.
set -eu

# Mark commits made by the loop so the gate applies containment (protected paths, banned
# patterns, preferences limits) to the worker but not to a human committing in their own shell.
export RALPH_LOOP=1

DEFAULT_MAX_ITERATIONS=2
DEFAULT_MAX_MINUTES=20
MAX_ITERATIONS=$DEFAULT_MAX_ITERATIONS
MAX_MINUTES=$DEFAULT_MAX_MINUTES

case "${1:-}" in
    ''|*[!0-9]*)
        ;;
    *)
        MAX_ITERATIONS=$1
        shift
        case "${1:-}" in
            ''|*[!0-9]*)
                ;;
            *)
                MAX_MINUTES=$1
                shift
                ;;
        esac
        ;;
esac

if [ "$#" -lt 1 ]; then
    echo "usage: harness/ralph.sh [max_iterations] [max_minutes_per_iteration] <agent command...>" >&2
    echo "defaults: max_iterations=$DEFAULT_MAX_ITERATIONS max_minutes_per_iteration=$DEFAULT_MAX_MINUTES" >&2
    exit 2
fi

TIMEOUT_COMMAND=
if command -v gtimeout > /dev/null 2>&1; then
    TIMEOUT_COMMAND=gtimeout
elif command -v timeout > /dev/null 2>&1; then
    TIMEOUT_COMMAND=timeout
else
    echo "ralph: missing timeout command; install gtimeout or timeout" >&2
    exit 2
fi

GIT_HOOK_KEY="core.hooks""Path"
uv run ralph install
HOOK_PATH=$(git config --get "$GIT_HOOK_KEY" 2>/dev/null || true)
if [ "$HOOK_PATH" != ".githooks" ]; then
    echo "ralph: local gate hook is not active after install" >&2
    exit 2
fi

TIMEOUT_SECONDS=$((MAX_MINUTES * 60))
mkdir -p scratchpad/runs
REGISTRY="scratchpad/ralph_runs.tsv"
if [ ! -f "$REGISTRY" ]; then
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
        "timestamp" "iteration" "pid" "status" "exit_code" "elapsed_seconds" \
        "stdout_path" "stderr_path" \
        > "$REGISTRY"
fi

i=1
while [ "$i" -le "$MAX_ITERATIONS" ]; do
    echo "ralph: iteration $i/$MAX_ITERATIONS" >&2
    RUN_STAMP=$(date -u +"%Y%m%dT%H%M%SZ")
    RUN_DIR="scratchpad/runs/$RUN_STAMP-$i"
    STDOUT_PATH="$RUN_DIR/stdout.log"
    STDERR_PATH="$RUN_DIR/stderr.log"
    mkdir -p "$RUN_DIR"
    START_SECONDS=$(date +%s)
    { sed -n '1,$p' PROMPT.md; printf '\nRALPH_ITERATION=%s/%s\n' "$i" "$MAX_ITERATIONS"; } | "$TIMEOUT_COMMAND" "$TIMEOUT_SECONDS" "$@" > "$STDOUT_PATH" 2> "$STDERR_PATH" &
    PID=$!
    set +e
    wait "$PID"
    EXIT_CODE=$?
    set -e
    END_SECONDS=$(date +%s)
    ELAPSED_SECONDS=$((END_SECONDS - START_SECONDS))
    TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

    if [ "$EXIT_CODE" -eq 0 ]; then
        STATUS=exited
    elif [ "$EXIT_CODE" -eq 124 ]; then
        STATUS=timeout
    else
        STATUS=failed
    fi

    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
        "$TIMESTAMP" "$i" "$PID" "$STATUS" "$EXIT_CODE" "$ELAPSED_SECONDS" \
        "$STDOUT_PATH" "$STDERR_PATH" \
        >> "$REGISTRY"

    if [ "$EXIT_CODE" -eq 124 ]; then
        echo "ralph: iteration $i exceeded the $MAX_MINUTES minute limit and was stopped. Common causes: long tests, stalled installs/network calls, interactive prompts, auth waits, or an agent still working. See $STDOUT_PATH and $STDERR_PATH." >&2
        exit 1
    elif [ "$EXIT_CODE" -ne 0 ]; then
        echo "ralph: worker exited with status $EXIT_CODE; stopping. The agent command failed or stopped early. See $STDOUT_PATH and $STDERR_PATH." >&2
        exit 1
    fi

    i=$((i + 1))
done

printf '%s %s %s\n' \
    "ralph: completed $MAX_ITERATIONS/$MAX_ITERATIONS iteration(s)." \
    "All worker commands exited 0, which means success." \
    "Ralph is stopping at the iteration limit; verify git status, commits, pushes, and merges separately." \
    >&2
exit 0
