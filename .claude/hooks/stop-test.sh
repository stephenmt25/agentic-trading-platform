#!/bin/bash
# Stop hook: runs unit tests when Claude finishes a turn IF Python files under
# services/ or libs/ have been modified. Throttled to at most one run per
# 15 minutes to avoid burning cycles on every single turn.
#
# Advisory only — prints results to stderr but always exits 0 (never blocks the
# model from stopping). Converts CLAUDE.md §9's prose verification mandate into
# mechanical post-turn enforcement.
#
# To make it strictly enforcing (fail closed), change `exit 0` at the bottom to
# `exit 2` when $TEST_EXIT -ne 0.

TRACK_DIR="${TEMP:-/tmp}/.claude-stop-test-aion"
mkdir -p "$TRACK_DIR"
COOLDOWN_FILE="$TRACK_DIR/last_run"
COOLDOWN_SECONDS=900  # 15 minutes

# Check cooldown
if [ -f "$COOLDOWN_FILE" ]; then
    LAST=$(cat "$COOLDOWN_FILE")
    NOW=$(python3 -c "import time; print(int(time.time()))" 2>/dev/null)
    if [ -n "$LAST" ] && [ -n "$NOW" ]; then
        ELAPSED=$((NOW - LAST))
        if [ "$ELAPSED" -lt "$COOLDOWN_SECONDS" ]; then
            exit 0
        fi
    fi
fi

# Only run if we're in the project root (guard against hooks firing elsewhere)
if [ ! -f "pyproject.toml" ] || [ ! -d "services" ] || [ ! -d "libs" ]; then
    exit 0
fi

# Only run if there are modified .py files under services/ or libs/
MODIFIED_PY=$(git diff --name-only 2>/dev/null | grep -E "^(services|libs)/.*\.py$" | head -5)
STAGED_PY=$(git diff --cached --name-only 2>/dev/null | grep -E "^(services|libs)/.*\.py$" | head -5)

if [ -z "$MODIFIED_PY" ] && [ -z "$STAGED_PY" ]; then
    exit 0
fi

# Resolve poetry — try PATH first, then known install location
POETRY="$(command -v poetry 2>/dev/null)"
if [ -z "$POETRY" ] || [ ! -x "$POETRY" ]; then
    POETRY="/c/Users/stevo/AppData/Local/Programs/Python/Python312/Scripts/poetry.exe"
fi
if [ ! -x "$POETRY" ]; then
    echo "🧪 stop-test hook: poetry not found — skipping" >&2
    exit 0
fi

echo "🧪 stop-test: running unit tests (python files modified)..." >&2
echo "    (throttled to 1 run / 15 min; skip next ${COOLDOWN_SECONDS}s)" >&2

# Record run time regardless of pass/fail so we don't thrash
python3 -c "import time; print(int(time.time()))" > "$COOLDOWN_FILE" 2>/dev/null

# Run unit tests, quiet mode, short traceback, per-test timeout
TEST_OUTPUT=$("$POETRY" run pytest tests/unit/ -q --tb=line --timeout=30 2>&1)
TEST_EXIT=$?

if [ $TEST_EXIT -eq 0 ]; then
    SUMMARY=$(echo "$TEST_OUTPUT" | tail -3)
    echo "✅ stop-test: unit tests passed." >&2
    echo "$SUMMARY" >&2
else
    echo "❌ stop-test: unit tests FAILED." >&2
    echo "$TEST_OUTPUT" | tail -25 >&2
    echo "" >&2
    echo "Fix the failures before declaring the task complete." >&2
fi

# Advisory only — always exit 0 to let the model stop.
exit 0
