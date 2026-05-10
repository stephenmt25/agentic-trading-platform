import { useAuthStore } from '../stores/authStore';
import { usePortfolioStore } from '../stores/portfolioStore';
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

class WebSocketClient {
    private socket: WebSocket | null = null;
    private reconnectAttempts = 0;
    private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
    private pingInterval: ReturnType<typeof setInterval> | null = null;

    connect() {
        if (this.socket?.readyState === WebSocket.OPEN) return;

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
                    case 'pubsub:pnl_updates':
                        usePortfolioStore.getState().updatePnlData(
                            data.profile_id,
                            {
                                position_id: data.position_id,
                                symbol: data.symbol,
                                net_post_tax: data.net_post_tax,
                                net_pre_tax: data.net_pre_tax,
                                pct_return: data.roi_pct,
                                gross_pnl: 0, fees: 0, tax_estimate: 0, // Mock fills
                                timestamp_us: data.timestamp_us
                            }
                        );
                        break;
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
                            const ts = data.trade_ts_ms || data.timestamp_us
                                ? Math.floor((data.timestamp_us ?? 0) / 1000) || data.trade_ts_ms
                                : Date.now();
                            useOrderBookStore.getState().ingest(
                                data.symbol,
                                data.exchange ?? 'BINANCE',
                                data.bids,
                                data.asks,
                                ts
                            );
                        }
                        break;
                    case 'pubsub:trades':
                        if (data.symbol && (data.side === 'bid' || data.side === 'ask')) {
                            useTapeStore.getState().ingest({
                                symbol: data.symbol,
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
        this.reconnectAttempts = 0;
    }
}

export const wsClient = new WebSocketClient();
