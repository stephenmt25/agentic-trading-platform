#!/usr/bin/env bash
# Praxis Trading Platform — Full System Launcher
# Usage: bash run_all.sh [--stop] [--local-frontend]
#
# Starts the 19 backend microservices on localhost. Frontend runs locally
# at http://localhost:3000 when --local-frontend is passed.
#
# --local-frontend  Also start the Next.js dev server on :3000.
# --stop            Gracefully stop all services and infrastructure.
#
# Prerequisites:
#   - Docker Desktop running (Redis + TimescaleDB)
#   - Poetry installed and in PATH
set -euo pipefail
cd "$(dirname "$0")"

# Resolve poetry — check common Windows paths (WSL /mnt/c and Git Bash /c)
POETRY=""
for p in \
    "/mnt/c/Users/stevo/AppData/Local/Programs/Python/Python312/Scripts/poetry.exe" \
    "/c/Users/stevo/AppData/Local/Programs/Python/Python312/Scripts/poetry.exe"; do
    [[ -f "$p" ]] && POETRY="$p" && break
done
[[ -n "$POETRY" ]] || POETRY="$(command -v poetry 2>/dev/null || true)"
[[ -n "$POETRY" ]] || { echo "ERROR: poetry not found"; exit 1; }

PIDFILE=".praxis_pids"
LOGDIR=".praxis_logs"

# ---------- Parse flags ----------
LOCAL_FRONTEND=false
for arg in "$@"; do
    case "$arg" in
        --stop) ;;  # handled below
        --local-frontend) LOCAL_FRONTEND=true ;;
    esac
done

# ---------- Stop mode ----------
if [[ "${1:-}" == "--stop" ]]; then
    echo "=== Stopping Praxis Trading Platform ==="
    # First: tracked PIDs from the current pidfile
    if [[ -f "$PIDFILE" ]]; then
        while read -r pid name; do
            if kill -0 "$pid" 2>/dev/null; then
                kill "$pid" 2>/dev/null && echo "  Stopped $name (PID $pid)" || true
            fi
        done < "$PIDFILE"
        rm -f "$PIDFILE"
    fi
    # Second: sweep any untracked zombie holding a known Praxis port.
    # This catches orphans from prior runs whose pidfile was already cleared.
    # Disable pipefail/errexit locally — grep returns 1 when a port is free,
    # which under `set -o pipefail` would abort the whole sweep silently.
    set +eo pipefail
    PRAXIS_PORTS="8000 8080 8081 8082 8083 8084 8085 8086 8087 8088 8089 8090 8091 8092 8093 8094 8095 8096"
    for port in $PRAXIS_PORTS; do
        holder_pid=$(netstat -ano 2>/dev/null | grep "[:.]${port} .*LISTEN" | awk '{print $5}' | head -1)
        if [[ -n "$holder_pid" ]]; then
            if kill "$holder_pid" 2>/dev/null || taskkill //PID "$holder_pid" //F >/dev/null 2>&1; then
                echo "  Swept zombie on :$port (PID $holder_pid)"
            else
                echo "  WARNING: Could not kill PID $holder_pid on :$port (may need elevated shell)"
            fi
        fi
    done
    set -eo pipefail
    docker compose -f deploy/docker-compose.yml down 2>/dev/null || true
    echo "=== All stopped ==="
    exit 0
fi

# ---------- Cleanup on exit ----------
cleanup() {
    echo ""
    echo "=== Shutting down (Ctrl+C caught) ==="
    if [[ -f "$PIDFILE" ]]; then
        while read -r pid name; do
            kill "$pid" 2>/dev/null || true
        done < "$PIDFILE"
        rm -f "$PIDFILE"
    fi
    docker compose -f deploy/docker-compose.yml down 2>/dev/null || true
    exit 0
}
trap cleanup SIGINT SIGTERM

# ---------- Prep ----------
mkdir -p "$LOGDIR"

# Pre-launch sweep: nukes ALL python.exe on the machine. Heavy hammer, but
# reliably clears Ctrl+C orphans that the pidfile missed. If you have unrelated
# Python work running (notebooks, other projects), stop it before running this.
if command -v taskkill >/dev/null 2>&1; then
    echo "=== Sweeping stale python.exe processes ==="
    if taskkill //F //IM python.exe >/dev/null 2>&1; then
        echo "  Cleared stale python.exe"
    else
        echo "  No stale python.exe to clear"
    fi
    rm -f "$PIDFILE"
    sleep 1
fi

# Guard against double-launch: if PID file still has live processes after the
# sweep (e.g. non-Python holders, taskkill missing), abort.
if [[ -f "$PIDFILE" ]]; then
    LIVE=0
    while read -r pid name; do
        kill -0 "$pid" 2>/dev/null && LIVE=$((LIVE + 1))
    done < "$PIDFILE"
    if [[ $LIVE -gt 0 ]]; then
        echo "ERROR: $LIVE service(s) still running from a previous launch."
        echo "  Run 'bash run_all.sh --stop' first, then try again."
        exit 1
    fi
    rm -f "$PIDFILE"
fi
> "$PIDFILE"

echo "============================================"
echo "   Praxis Trading Platform — Full Startup"
echo "============================================"
echo ""

# ---------- 1. Infrastructure ----------
echo "=== [1/4] Starting Infrastructure (Redis + TimescaleDB) ==="
docker compose -f deploy/docker-compose.yml up -d
echo "  Waiting for services to be healthy..."

# Wait for Redis
for i in $(seq 1 30); do
    if docker compose -f deploy/docker-compose.yml exec -T redis redis-cli -a changeme_redis_dev ping 2>/dev/null | grep -q PONG; then
        echo "  Redis: ready"
        break
    fi
    if [[ $i -eq 30 ]]; then echo "  ERROR: Redis failed to start"; exit 1; fi
    sleep 1
done

# Wait for TimescaleDB
for i in $(seq 1 30); do
    if docker compose -f deploy/docker-compose.yml exec -T timescaledb pg_isready -U postgres -d praxis_trading 2>/dev/null | grep -q "accepting"; then
        echo "  TimescaleDB: ready"
        break
    fi
    if [[ $i -eq 30 ]]; then echo "  ERROR: TimescaleDB failed to start"; exit 1; fi
    sleep 1
done
echo ""

# ---------- 2. Migrations ----------
echo "=== [2/4] Running Database Migrations ==="
$POETRY run python scripts/migrate.py
echo ""

# ---------- Helper: check port availability ----------
check_port() {
    local port=$1
    local name=$2
    if netstat -ano 2>/dev/null | grep -q "[:.]${port} .*LISTEN"; then
        local holder_pid=$(netstat -ano 2>/dev/null | grep "[:.]${port} .*LISTEN" | awk '{print $5}' | head -1)
        echo "  WARNING: Port $port ($name) already in use by PID $holder_pid — killing it"
        kill "$holder_pid" 2>/dev/null || taskkill //PID "$holder_pid" //F 2>/dev/null || true
        sleep 1
        # Verify the kill actually freed the port — fail loudly if not
        if netstat -ano 2>/dev/null | grep -q "[:.]${port} .*LISTEN"; then
            echo "  ERROR: Port $port still held after kill. Run 'taskkill //F //PID $holder_pid' in an elevated shell, then retry."
            exit 1
        fi
    fi
}

# ---------- Helper: launch a background service ----------
launch() {
    local name=$1
    local module=$2
    local port=$3

    check_port "$port" "$name"
    echo "  Starting $name on :$port"
    $POETRY run python -m $module > "$LOGDIR/$name.log" 2>&1 &
    local pid=$!
    echo "$pid $name" >> "$PIDFILE"
}

launch_async() {
    local name=$1
    local module=$2

    echo "  Starting $name (async worker)"
    $POETRY run python -m $module > "$LOGDIR/$name.log" 2>&1 &
    local pid=$!
    echo "$pid $name" >> "$PIDFILE"
}

# Verify recently launched processes are still alive after a brief settle
verify_launches() {
    local failures=0
    sleep 3
    while read -r pid name; do
        if ! kill -0 "$pid" 2>/dev/null; then
            echo "  ERROR: $name (PID $pid) crashed on startup. Check $LOGDIR/$name.log"
            failures=$((failures + 1))
        fi
    done < "$PIDFILE"
    if [[ $failures -gt 0 ]]; then
        echo ""
        echo "  WARNING: $failures service(s) failed to start. Review logs above."
    fi
}

# ---------- 3. Backend Services ----------
echo "=== [3/4] Starting Backend Services ==="

# Core pipeline (order matters: validation -> hot_path -> execution)
launch "validation"    "services.validation.src.main"    8081
sleep 2  # hot_path waits for validation health
launch "hot_path"      "services.hot_path.src.main"      8082
launch "execution"     "services.execution.src.main"     8083
launch "pnl"           "services.pnl.src.main"           8084

# Supporting services
launch "api_gateway"   "services.api_gateway.src.main"   8000
launch "ingestion"     "services.ingestion.src.main"     8080
launch "logger"        "services.logger.src.main"        8085
launch "backtesting"   "services.backtesting.src.main"   8086
launch "analyst"       "services.analyst.src.main"       8087
launch "archiver"      "services.archiver.src.main"      8088
launch "tax"           "services.tax.src.main"           8089

# ML agents
launch "ta_agent"      "services.ta_agent.src.main"      8090
launch "regime_hmm"    "services.regime_hmm.src.main"    8091
launch "sentiment"     "services.sentiment.src.main"     8092
launch "risk"          "services.risk.src.main"          8093
launch "debate"        "services.debate.src.main"        8096

# Infrastructure services
launch "rate_limiter" "services.rate_limiter.src.main" 8094
launch "slm_inference" "services.slm_inference.src.main" 8095

# Standalone async services (no HTTP server)
launch_async "strategy"     "services.strategy.src.main"

# Daily paper-trading report daemon: runs a backfill on startup, then
# regenerates each completed UTC day at 00:05 UTC. Idempotent (upsert).
echo "  Starting daily_report (daemon)"
$POETRY run python scripts/daily_report.py --daemon > "$LOGDIR/daily_report.log" 2>&1 &
echo "$! daily_report" >> "$PIDFILE"

echo ""

# Verify all services are still alive after settling
verify_launches

# Health gate: confirm API gateway is actually responding
echo ""
echo "  Checking API gateway health..."
for i in $(seq 1 10); do
    if curl -s http://localhost:8000/health 2>/dev/null | grep -q "healthy"; then
        echo "  API Gateway: healthy"
        break
    fi
    if [[ $i -eq 10 ]]; then
        echo "  WARNING: API Gateway not responding on :8000. Check $LOGDIR/api_gateway.log"
    fi
    sleep 1
done

# ---------- 4. Local Frontend (optional) ----------
if [[ "$LOCAL_FRONTEND" == true ]]; then
    echo "=== [4/4] Starting Local Frontend (Next.js) ==="
    rm -f frontend/.next/dev/lock 2>/dev/null
    if command -v powershell.exe >/dev/null 2>&1; then
        powershell.exe -Command "Get-NetTCPConnection -LocalPort 3000 -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique | Where-Object { \$_ -ne 0 } | ForEach-Object { Stop-Process -Id \$_ -Force -ErrorAction SilentlyContinue }" 2>/dev/null
    fi
    sleep 1
    cd frontend
    npm run dev > "../$LOGDIR/frontend.log" 2>&1 &
    FRONTEND_PID=$!
    echo "$FRONTEND_PID frontend" >> "../$PIDFILE"
    cd ..
    echo "  Frontend starting on :3000"
    echo ""
fi

# ---------- Summary ----------
echo "============================================"
echo "   All services launched!"
echo "============================================"
echo ""
echo "  Backend Ports:"
echo "    API Gateway .... http://localhost:8000"
echo "    Ingestion ...... :8080"
echo "    Validation ..... :8081"
echo "    Hot Path ....... :8082"
echo "    Execution ...... :8083"
echo "    PnL ............ :8084"
echo "    Logger ......... :8085"
echo "    Backtesting .... :8086"
echo "    Analyst ........ :8087"
echo "    Archiver ....... :8088"
echo "    Tax ............ :8089"
echo "    TA Agent ....... :8090"
echo "    Regime HMM ..... :8091"
echo "    Sentiment ...... :8092"
echo "    Risk ........... :8093"
echo "    Rate Limiter ... :8094"
echo "    SLM Inference .. :8095"
echo "    Debate ......... :8096"
echo ""
if [[ "$LOCAL_FRONTEND" == true ]]; then
    echo "  Frontend:       http://localhost:3000"
    echo ""
fi
echo "  Logs: $LOGDIR/"
echo "  Stop: bash run_all.sh --stop"
echo ""
echo "  Press Ctrl+C to stop everything."
echo ""

# Keep script alive so Ctrl+C works
set +e
while true; do
    sleep 60
done
