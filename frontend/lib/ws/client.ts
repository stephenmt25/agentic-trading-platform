import { useAuthStore } from '../stores/authStore';
import { usePortfolioStore, PnLPositionSnapshot } from '../stores/portfolioStore';
import { useAlertStore } from '../stores/alertStore';
import { useHITLStore } from '../stores/hitlStore';
import { useConnectionStore } from '../stores/connectionStore';
import { useAgentViewStore } from '../stores/agentViewStore';
import { useOrderBookStore } from '../stores/orderbookStore';
import { useTapeStore } from '../stores/tapeStore';
import { BACKEND_DIRECT_URL } from '../api/client';

function getWsUrl(): string {
    // WebSocket must connect directly to the backend (Vercel can't proxy WS)
    return BACKEND_DIRECT_URL.replace(/^http/, 'ws') + '/ws';
}

// ── PnL wire parsing (FE-W2) ─────────────────────────────────────────────
// Decimal fields are str-encoded on the wire (registry row 54). Missing or
// unparseable values become null — consumers null-guard.
function toNumberOrNull(value: unknown): number | null {
    if (value === null || value === undefined || value === '') return null;
    const n = Number(value);
    return Number.isFinite(n) ? n : null;
}

// Exported for tests. Returns null when the message has no position_id —
// PNL_UPDATE events are per-position and the store keys on it.
export function parsePnlMessage(data: any): PnLPositionSnapshot | null {
    if (!data || typeof data !== 'object' || !data.position_id) return null;
    return {
        position_id: String(data.position_id),
        profile_id: data.profile_id ? String(data.profile_id) : '',
        symbol: data.symbol ? String(data.symbol) : '',
        gross_pnl: toNumberOrNull(data.gross_pnl),
        fees: toNumberOrNull(data.fees),
        net_pre_tax: toNumberOrNull(data.net_pre_tax),
        net_post_tax: toNumberOrNull(data.net_post_tax),
        tax_estimate: toNumberOrNull(data.tax_estimate),
        pct_return: toNumberOrNull(data.pct_return),
        timestamp_us: toNumberOrNull(data.timestamp_us) ?? Date.now() * 1000,
    };
}

class WebSocketClient {
    private socket: WebSocket | null = null;
    private reconnectAttempts = 0;
    private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
    private pingInterval: ReturnType<typeof setInterval> | null = null;

    // FE-W2 render-jank fix at the source: buffer latest-per-position and
    // flush to the store at most every 250ms — ONE zustand set() per flush
    // instead of one per message. Single timer, started on the first
    // buffered item; cleared when the buffer empties / on disconnect.
    private static readonly PNL_FLUSH_INTERVAL_MS = 250;
    private pnlBuffer = new Map<string, PnLPositionSnapshot>();
    private pnlFlushTimer: ReturnType<typeof setTimeout> | null = null;

    private bufferPnlSnapshot(snapshot: PnLPositionSnapshot) {
        this.pnlBuffer.set(snapshot.position_id, snapshot);
        if (this.pnlFlushTimer === null) {
            this.pnlFlushTimer = setTimeout(
                () => this.flushPnlBuffer(),
                WebSocketClient.PNL_FLUSH_INTERVAL_MS
            );
        }
    }

    private flushPnlBuffer() {
        this.pnlFlushTimer = null;
        if (this.pnlBuffer.size === 0) return;
        const snapshots = Array.from(this.pnlBuffer.values());
        this.pnlBuffer.clear();
        usePortfolioStore.getState().applyPnlSnapshots(snapshots);
    }

    private clearPnlBuffer() {
        if (this.pnlFlushTimer) {
            clearTimeout(this.pnlFlushTimer);
            this.pnlFlushTimer = null;
        }
        this.pnlBuffer.clear();
    }

    connect() {
        // Guard CONNECTING too — a second connect() during the handshake
        // would orphan the first socket, whose onclose then schedules a
        // reconnect and leaves two live sockets.
        if (
            this.socket &&
            (this.socket.readyState === WebSocket.OPEN ||
                this.socket.readyState === WebSocket.CONNECTING)
        ) {
            return;
        }
        // A deliberate connect supersedes any pending backoff reconnect.
        if (this.reconnectTimer) {
            clearTimeout(this.reconnectTimer);
            this.reconnectTimer = null;
        }

        const token = useAuthStore.getState().jwt;
        if (!token) return;

        const wsUrl = `${getWsUrl()}?token=${encodeURIComponent(token)}`;
        this.socket = new WebSocket(wsUrl);

        this.socket.onopen = () => {
            this.reconnectAttempts = 0;
            useConnectionStore.getState().setConnected();
            this.startHeartbeat();
        };

        this.socket.onmessage = (event) => {
            if (event.data === 'pong') return;
            try {
                const msg = JSON.parse(event.data);
                const data = msg.data;

                switch (msg.channel) {
                    case 'pubsub:pnl_updates': {
                        const snapshot = parsePnlMessage(data);
                        if (snapshot) this.bufferPnlSnapshot(snapshot);
                        break;
                    }
                    case 'pubsub:system_alerts':
                        useAlertStore.getState().addAlert({
                            event_id: Math.random().toString(),
                            timestamp_us: Date.now() * 1000,
                            source_service: 'system',
                            verdict: data.level === 'RED' ? 'RED' : 'AMBER',
                            check_type: 'ESCALATION',
                            mode: 'ASYNC',
                            reason: data.reason
                        });
                        break;
                    case 'pubsub:hitl_pending':
                        useHITLStore.getState().addRequest({
                            event_id: data.event_id,
                            profile_id: data.profile_id,
                            symbol: data.symbol,
                            side: data.side,
                            quantity: data.quantity,
                            price: data.price,
                            confidence: data.confidence,
                            trigger_reason: data.trigger_reason,
                            agent_scores: data.agent_scores || {},
                            risk_metrics: data.risk_metrics || {},
                            timestamp_us: data.timestamp_us,
                            status: 'PENDING',
                        });
                        break;
                    case 'pubsub:alerts':
                        // Phase 3: regime disagreement and other alerts
                        useAlertStore.getState().addAlert({
                            event_id: data.event_id || Math.random().toString(),
                            timestamp_us: data.timestamp_us || Date.now() * 1000,
                            source_service: data.source_service || 'hot-path',
                            verdict: data.level === 'RED' ? 'RED' : 'AMBER',
                            check_type: data.event_type || 'REGIME_DISAGREEMENT',
                            mode: 'ASYNC',
                            reason: data.message || data.reason
                        });
                        break;
                    case 'pubsub:agent_telemetry':
                        if (data.agent_id && data.event_type) {
                            useAgentViewStore.getState().ingestEvent(data);
                        }
                        break;
                    case 'pubsub:orderbook':
                        if (data.symbol && Array.isArray(data.bids) && Array.isArray(data.asks)) {
                            // Decimal values arrive as strings via msgpack default=str.
                            // Normalize CCXT's "BTC/USDT" to URL-safe "BTC-USDT" so it
                            // matches the symbol shape used by /hot/[symbol] routes.
                            const symbol = String(data.symbol).replace('/', '-').toUpperCase();
                            const ts = data.trade_ts_ms || data.timestamp_us
                                ? Math.floor((data.timestamp_us ?? 0) / 1000) || data.trade_ts_ms
                                : Date.now();
                            useOrderBookStore.getState().ingest(
                                symbol,
                                data.exchange ?? 'BINANCE',
                                data.bids,
                                data.asks,
                                ts
                            );
                        }
                        break;
                    case 'pubsub:trades':
                        if (data.symbol && (data.side === 'bid' || data.side === 'ask')) {
                            const symbol = String(data.symbol).replace('/', '-').toUpperCase();
                            useTapeStore.getState().ingest({
                                symbol,
                                exchange: data.exchange ?? 'BINANCE',
                                side: data.side,
                                price: data.price,
                                size: data.size,
                                timestampMs: data.trade_ts_ms ?? Math.floor((data.timestamp_us ?? 0) / 1000) ?? Date.now(),
                                tradeId: data.trade_id ?? null,
                            });
                        }
                        break;
                }
            } catch (e) {
                console.error('WS Parse error', e);
            }
        };

        this.socket.onerror = () => {
            // WS failures don't mark backend as offline — API health is
            // the source of truth. WS is a nice-to-have for live updates.
        };

        this.socket.onclose = () => {
            this.stopHeartbeat();
            this.socket = null;
            if (useAuthStore.getState().isAuthenticated) {
                this.attemptReconnect();
            }
        };
    }

    private startHeartbeat() {
        this.pingInterval = setInterval(() => {
            if (this.socket?.readyState === WebSocket.OPEN) {
                this.socket.send('ping');
            }
        }, 30000); // 30s
    }

    private stopHeartbeat() {
        if (this.pingInterval) {
            clearInterval(this.pingInterval);
            this.pingInterval = null;
        }
    }

    private attemptReconnect() {
        // Unlimited retries with exponential backoff (max 60s) + jitter
        const base = Math.min(Math.pow(2, this.reconnectAttempts) * 1000, 60000);
        const jitter = base * 0.2 * Math.random();
        const delay = base + jitter;
        this.reconnectTimer = setTimeout(() => this.connect(), delay);
        this.reconnectAttempts++;
    }

    isConnected(): boolean {
        return this.socket?.readyState === WebSocket.OPEN;
    }

    disconnect() {
        if (this.reconnectTimer) {
            clearTimeout(this.reconnectTimer);
            this.reconnectTimer = null;
        }
        if (this.socket) {
            this.socket.close();
            this.socket = null;
        }
        this.stopHeartbeat();
        this.clearPnlBuffer();
        this.reconnectAttempts = 0;
    }
}

export const wsClient = new WebSocketClient();
