#!/bin/bash
# PreToolUse hook: validates Edit tool calls before execution.
# Blocks bad edits with helpful error messages (exit 2).
#
# Trimmed 2026-04-15 — removed the old_string-match check (never fired in 18 sessions;
# Claude Code's Edit tool already validates this natively). Kept the float() check
# as cheap insurance (catastrophic cost if missed, ~0 cost if no match) and the
# invented-channel check (proven to catch real bugs).

INPUT=$(cat)
TOOL_NAME=$(echo "$INPUT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('tool_name',''))" 2>/dev/null)

# Only validate Edit tool
if [ "$TOOL_NAME" != "Edit" ]; then
    exit 0
fi

FILE_PATH=$(echo "$INPUT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('tool_input',{}).get('file_path',''))" 2>/dev/null)
OLD_STRING=$(echo "$INPUT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('tool_input',{}).get('old_string',''))" 2>/dev/null)
NEW_STRING=$(echo "$INPUT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('tool_input',{}).get('new_string',''))" 2>/dev/null)

# --- Check 1: Financial code anti-pattern detection (float in Decimal-mandated paths) ---
if [[ "$FILE_PATH" == *.py ]]; then
    SENSITIVE=false
    for pattern in execution pnl risk strategy; do
        if echo "$FILE_PATH" | grep -qi "$pattern"; then
            SENSITIVE=true
            break
        fi
    done

    if [ "$SENSITIVE" = "true" ] && [ -n "$NEW_STRING" ]; then
        HAS_FLOAT=$(echo "$NEW_STRING" | grep -c "float(" 2>/dev/null)
        if [ "$HAS_FLOAT" -gt 0 ]; then
            OLD_FLOAT=$(echo "$OLD_STRING" | grep -c "float(" 2>/dev/null)
            if [ "$HAS_FLOAT" -gt "$OLD_FLOAT" ]; then
                echo '{"decision": "block", "reason": "EDIT VALIDATOR: You are introducing float() in financial code ('"$FILE_PATH"'). Use Decimal from libs/core/types.py instead. See CLAUDE.md §2A."}'
                exit 2
            fi
        fi
    fi
fi

# --- Check 2: Channel name invention detection ---
if [[ "$FILE_PATH" == *.py ]] && [ -n "$NEW_STRING" ]; then
    CHANNELS_FILE="libs/messaging/channels.py"
    if [ -f "$CHANNELS_FILE" ]; then
        NEW_CHANNELS=$(echo "$NEW_STRING" | grep -oE '(stream:|pubsub:)[a-z_]+' 2>/dev/null)
        if [ -n "$NEW_CHANNELS" ]; then
            while IFS= read -r ch; do
                if ! grep -q "$ch" "$CHANNELS_FILE" 2>/dev/null; then
                    echo '{"decision": "block", "reason": "EDIT VALIDATOR: Channel name '"'$ch'"' not found in libs/messaging/channels.py. Do not invent channel names. See CLAUDE.md §2B."}'
                    exit 2
                fi
            done <<< "$NEW_CHANNELS"
        fi
    fi
fi

# All checks passed
exit 0
