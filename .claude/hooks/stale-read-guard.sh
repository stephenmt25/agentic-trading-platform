#!/bin/bash
# PreToolUse hook: blocks Edit/Write if the file hasn't been Read or is stale
# Replicates ForgeCode's stale-read detection pattern (~+3% on Terminal-Bench)

TRACK_DIR="${TEMP:-/tmp}/.claude-stale-guard-aion"
mkdir -p "$TRACK_DIR"

# Parse tool input from stdin (Claude Code passes JSON)
INPUT=$(cat)
TOOL_NAME=$(echo "$INPUT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('tool_name',''))" 2>/dev/null)
FILE_PATH=$(echo "$INPUT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('tool_input',{}).get('file_path',''))" 2>/dev/null)

# Only guard Edit and Write tools
if [ "$TOOL_NAME" != "Edit" ] && [ "$TOOL_NAME" != "Write" ]; then
    exit 0
fi

if [ -z "$FILE_PATH" ]; then
    exit 0
fi

# Allow new file creation (Write to non-existent file is fine)
if [ ! -f "$FILE_PATH" ]; then
    exit 0
fi

# Check if we have a read record for this file
TRACK_FILE=$(echo "$FILE_PATH" | python3 -c "import sys,hashlib; print(hashlib.md5(sys.stdin.read().strip().encode()).hexdigest())")

if [ ! -f "$TRACK_DIR/$TRACK_FILE" ]; then
    # File exists but was never Read in this session
    echo '{"decision": "block", "reason": "STALE-READ GUARD: You are editing '"$FILE_PATH"' but have not Read it in this session. Read the file first to ensure you have current context."}'
    exit 2
fi

# Check if file was modified since last Read
LAST_READ=$(cat "$TRACK_DIR/$TRACK_FILE")
FILE_MTIME=$(python3 -c "import os; print(int(os.path.getmtime(r'$FILE_PATH')))" 2>/dev/null)

if [ -n "$FILE_MTIME" ] && [ -n "$LAST_READ" ] && [ "$FILE_MTIME" -gt "$LAST_READ" ]; then
    echo '{"decision": "block", "reason": "STALE-READ GUARD: '"$FILE_PATH"' was modified since you last Read it. Re-read the file to get current contents before editing."}'
    exit 2
fi

# File was Read and hasn't been modified since — allow the edit
exit 0
