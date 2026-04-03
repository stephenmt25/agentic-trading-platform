#!/bin/bash
# PostToolUse hook: tracks when files are Read for stale-read detection
# Companion to stale-read-guard.sh

TRACK_DIR="${TEMP:-/tmp}/.claude-stale-guard-aion"
mkdir -p "$TRACK_DIR"

# Parse tool input from stdin (Claude Code passes JSON)
INPUT=$(cat)
TOOL_NAME=$(echo "$INPUT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('tool_name',''))" 2>/dev/null)
FILE_PATH=$(echo "$INPUT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('tool_input',{}).get('file_path',''))" 2>/dev/null)

# Only track Read tool
if [ "$TOOL_NAME" != "Read" ] || [ -z "$FILE_PATH" ]; then
    exit 0
fi

# Sanitize file path to flat filename for tracking
TRACK_FILE=$(echo "$FILE_PATH" | python3 -c "import sys,hashlib; print(hashlib.md5(sys.stdin.read().strip().encode()).hexdigest())")

# Record current timestamp
python3 -c "import time; print(int(time.time()))" > "$TRACK_DIR/$TRACK_FILE"

exit 0
