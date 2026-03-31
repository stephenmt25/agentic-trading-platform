#!/usr/bin/env bash
# Praxis Trading Platform — Full System Launcher
# Usage: bash run_all.sh [--stop] [--with-tunnel] [--local-frontend]
#
# Frontend is deployed on Vercel. This script starts backend services only.
# Use --with-tunnel to also start a Cloudflare Tunnel for Vercel connectivity.
# Use --local-frontend to also start the local Next.js dev server on :3000.
set -uo pipefail
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
WITH_TUNNEL=false
LOCAL_FRONTEND=false
for arg in "$@"; do
    case "$arg" in
        --stop) ;;  # handled below
        --with-tunnel) WITH_TUNNEL=true ;;
        --local-frontend) LOCAL_FRONTEND=true ;;
    esac
done

# ---------- Stop mode ----------
if [[ "${1:-}" == "--stop" ]]; then
    echo "=== Stopping Praxis Trading Platform ==="
    if [[ -f "$PIDFILE" ]]; then
        while read -r pid name; do
            if kill -0 "$pid" 2>/dev/null; then
                kill "$pid" 2>/dev/null && echo "  Stopped $name (PID $pid)" || true
            fi
        done < "$PIDFILE"
        rm -f "$PIDFILE"
    fi
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

# ---------- Helper: launch a background service ----------
launch() {
    local name=$1
    local module=$2
    local port=$3

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

# Standalone async services (no HTTP server)
launch_async "strategy"     "services.strategy.src.main"
launch "rate_limiter" "services.rate_limiter.src.main" 8094

echo ""

# ---------- 4. Cloudflare Tunnel (optional) ----------
if [[ "$WITH_TUNNEL" == true ]]; then
    echo "=== [4/5] Starting Cloudflare Tunnel ==="
    CLOUDFLARED=""
    for p in \
        "/c/Program Files (x86)/cloudflared/cloudflared.exe" \
        "/mnt/c/Program Files (x86)/cloudflared/cloudflared.exe"; do
        [[ -f "$p" ]] && CLOUDFLARED="$p" && break
    done
    [[ -n "$CLOUDFLARED" ]] || CLOUDFLARED="$(command -v cloudflared 2>/dev/null || true)"
    if [[ -n "$CLOUDFLARED" ]]; then
        "$CLOUDFLARED" tunnel --url http://localhost:8000 > "$LOGDIR/cloudflared.log" 2>&1 &
        TUNNEL_PID=$!
        echo "$TUNNEL_PID cloudflared" >> "$PIDFILE"
        sleep 6
        TUNNEL_URL=$(grep -o 'https://[a-z0-9-]*\.trycloudflare\.com' "$LOGDIR/cloudflared.log" | head -1)
        if [[ -n "$TUNNEL_URL" ]]; then
            echo "  Tunnel: $TUNNEL_URL"
            echo "  Update NEXT_PUBLIC_API_URL on Vercel if the URL changed."
        else
            echo "  WARNING: Tunnel started but URL not detected. Check $LOGDIR/cloudflared.log"
        fi
    else
        echo "  WARNING: cloudflared not found. Install with: winget install Cloudflare.cloudflared"
        echo "  Skipping tunnel — Vercel frontend will show Backend Offline."
    fi
    echo ""
fi

# ---------- 5. Local Frontend (optional) ----------
if [[ "$LOCAL_FRONTEND" == true ]]; then
    echo "=== Starting Local Frontend (Next.js) ==="
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
echo "    Debate ......... :8096"
echo ""
echo "  Frontend:"
if [[ "$LOCAL_FRONTEND" == true ]]; then
    echo "    Local .......... http://localhost:3000"
fi
echo "    Vercel ......... https://frontend-seven-khaki-13.vercel.app"
if [[ "$WITH_TUNNEL" == true ]] && [[ -n "${TUNNEL_URL:-}" ]]; then
    echo "    Tunnel ......... $TUNNEL_URL"
fi
echo ""
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
