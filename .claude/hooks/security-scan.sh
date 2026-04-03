#!/bin/bash
# PostToolUse hook: scans edited Python files for security vulnerabilities
# Replicates Droid's security-first pattern (100% on tbench security tasks)
# Advisory only — warns but never blocks (exit 0 always)

INPUT=$(cat)
TOOL_NAME=$(echo "$INPUT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('tool_name',''))" 2>/dev/null)
FILE_PATH=$(echo "$INPUT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('tool_input',{}).get('file_path',''))" 2>/dev/null)

# Only scan Edit/Write on .py files
if [ "$TOOL_NAME" != "Edit" ] && [ "$TOOL_NAME" != "Write" ]; then
    exit 0
fi

if [[ ! "$FILE_PATH" == *.py ]]; then
    exit 0
fi

# Only scan security-sensitive paths
SENSITIVE=false
for pattern in execution pnl risk strategy api_gateway rate_limiter exchange auth; do
    if echo "$FILE_PATH" | grep -qi "$pattern"; then
        SENSITIVE=true
        break
    fi
done

if [ "$SENSITIVE" != "true" ]; then
    exit 0
fi

# File must exist to scan
if [ ! -f "$FILE_PATH" ]; then
    exit 0
fi

WARNINGS=""

# 1. float() in financial code (should be Decimal)
FLOAT_HITS=$(grep -n "float(" "$FILE_PATH" 2>/dev/null | grep -v "^#" | grep -v "# noqa" | head -3)
if [ -n "$FLOAT_HITS" ]; then
    WARNINGS="${WARNINGS}\n⚠️  FLOAT in financial code (use Decimal):\n${FLOAT_HITS}\n"
fi

# 2. SQL string formatting (injection risk)
SQL_HITS=$(grep -nE "(f\"|f').*?(SELECT|INSERT|UPDATE|DELETE|DROP|CREATE)" "$FILE_PATH" 2>/dev/null | head -3)
if [ -z "$SQL_HITS" ]; then
    SQL_HITS=$(grep -nE "\.format\(.*?(SELECT|INSERT|UPDATE|DELETE)" "$FILE_PATH" 2>/dev/null | head -3)
fi
if [ -n "$SQL_HITS" ]; then
    WARNINGS="${WARNINGS}\n🔴 SQL INJECTION RISK (use parameterized queries):\n${SQL_HITS}\n"
fi

# 3. Hardcoded credentials
CRED_HITS=$(grep -nEi "(password|secret|api_key|token)\s*=\s*['\"]" "$FILE_PATH" 2>/dev/null | grep -v "settings\." | grep -v "os\.environ" | grep -v "os\.getenv" | head -3)
if [ -n "$CRED_HITS" ]; then
    WARNINGS="${WARNINGS}\n🔴 HARDCODED CREDENTIALS:\n${CRED_HITS}\n"
fi

# 4. Raw JSON without Pydantic validation
RAW_JSON=$(grep -nE "(request\.json|json\.loads)" "$FILE_PATH" 2>/dev/null | grep -v "BaseModel" | grep -v "schema" | head -3)
if [ -n "$RAW_JSON" ]; then
    WARNINGS="${WARNINGS}\n⚠️  RAW JSON (validate with Pydantic BaseModel):\n${RAW_JSON}\n"
fi

# 5. Exception detail leakage (outside logging)
LEAK_HITS=$(grep -nE "(str\(e\)|repr\(e\)|traceback\.format)" "$FILE_PATH" 2>/dev/null | grep -v "logger\." | grep -v "log\." | grep -v "logging\." | head -3)
if [ -n "$LEAK_HITS" ]; then
    WARNINGS="${WARNINGS}\n⚠️  EXCEPTION DETAIL LEAKAGE (sanitize error responses):\n${LEAK_HITS}\n"
fi

# Output warnings if any found
if [ -n "$WARNINGS" ]; then
    echo -e "\n🛡️  SECURITY SCAN — $(basename "$FILE_PATH")${WARNINGS}" >&2
    echo -e "📋 Run CLAUDE.md Section 12 security checklist for this file.\n" >&2
fi

# Always exit 0 — advisory only
exit 0
