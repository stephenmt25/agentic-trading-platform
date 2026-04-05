#!/bin/bash
# PreToolUse hook: validates Edit tool calls before execution
# Replicates ForgeCode's tool-call correction layer (~+2-3%)
# Blocks bad edits with helpful error messages (exit 2)

INPUT=$(cat)
TOOL_NAME=$(echo "$INPUT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('tool_name',''))" 2>/dev/null)

# Only validate Edit tool
if [ "$TOOL_NAME" != "Edit" ]; then
    exit 0
fi

FILE_PATH=$(echo "$INPUT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('tool_input',{}).get('file_path',''))" 2>/dev/null)
OLD_STRING=$(echo "$INPUT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('tool_input',{}).get('old_string',''))" 2>/dev/null)
NEW_STRING=$(echo "$INPUT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('tool_input',{}).get('new_string',''))" 2>/dev/null)

# --- Check 1: File must exist ---
if [ -n "$FILE_PATH" ] && [ ! -f "$FILE_PATH" ]; then
    echo '{"decision": "block", "reason": "EDIT VALIDATOR: File '"$FILE_PATH"' does not exist. Check the path and try again."}'
    exit 2
fi

# --- Check 2: old_string must exist in the file ---
if [ -n "$OLD_STRING" ] && [ -n "$FILE_PATH" ] && [ -f "$FILE_PATH" ]; then
    # Use python for reliable multiline string matching
    MATCH=$(python3 -c "
import sys
old = '''$OLD_STRING''' if len('''$OLD_STRING''') < 500 else sys.exit(0)
try:
    content = open(r'$FILE_PATH', 'r', encoding='utf-8').read()
    if old not in content:
        print('NOT_FOUND')
except:
    pass
" 2>/dev/null)

    # Fallback: use python with stdin for reliability with special chars
    if [ -z "$MATCH" ]; then
        MATCH=$(echo "$INPUT" | python3 -c "
import sys, json
d = json.load(sys.stdin)
old = d.get('tool_input',{}).get('old_string','')
fp = d.get('tool_input',{}).get('file_path','')
if old and fp:
    try:
        content = open(fp, 'r', encoding='utf-8').read()
        if old not in content:
            print('NOT_FOUND')
    except:
        pass
" 2>/dev/null)
    fi

    if [ "$MATCH" = "NOT_FOUND" ]; then
        echo '{"decision": "block", "reason": "EDIT VALIDATOR: The old_string was not found in '"$FILE_PATH"'. Re-read the file to get current contents, then retry with the exact text."}'
        exit 2
    fi
fi

# --- Check 3: Financial code anti-pattern detection ---
if [[ "$FILE_PATH" == *.py ]]; then
    SENSITIVE=false
    for pattern in execution pnl risk strategy; do
        if echo "$FILE_PATH" | grep -qi "$pattern"; then
            SENSITIVE=true
            break
        fi
    done

    if [ "$SENSITIVE" = "true" ] && [ -n "$NEW_STRING" ]; then
        # Check for float() introduction in financial code
        HAS_FLOAT=$(echo "$NEW_STRING" | grep -c "float(" 2>/dev/null)
        if [ "$HAS_FLOAT" -gt 0 ]; then
            # Verify it's not already in old_string (i.e., we're adding it, not just moving it)
            OLD_FLOAT=$(echo "$OLD_STRING" | grep -c "float(" 2>/dev/null)
            if [ "$HAS_FLOAT" -gt "$OLD_FLOAT" ]; then
                echo '{"decision": "block", "reason": "EDIT VALIDATOR: You are introducing float() in financial code ('"$FILE_PATH"'). Use Decimal from libs/core/types.py instead. See CLAUDE.md Section 5A."}'
                exit 2
            fi
        fi
    fi
fi

# --- Check 4: Channel name invention detection ---
if [[ "$FILE_PATH" == *.py ]] && [ -n "$NEW_STRING" ]; then
    # Check if new_string introduces string literals that look like channel names
    CHANNELS_FILE="libs/messaging/channels.py"
    if [ -f "$CHANNELS_FILE" ]; then
        NEW_CHANNELS=$(echo "$NEW_STRING" | grep -oE '(stream:|pubsub:)[a-z_]+' 2>/dev/null)
        if [ -n "$NEW_CHANNELS" ]; then
            while IFS= read -r ch; do
                if ! grep -q "$ch" "$CHANNELS_FILE" 2>/dev/null; then
                    echo '{"decision": "block", "reason": "EDIT VALIDATOR: Channel name '"'$ch'"' not found in libs/messaging/channels.py. Do not invent channel names. See CLAUDE.md Section 5B."}'
                    exit 2
                fi
            done <<< "$NEW_CHANNELS"
        fi
    fi
fi

# All checks passed
exit 0
