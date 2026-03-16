import { useAuthStore } from '../stores/authStore';
import { usePortfolioStore } from '../stores/portfolioStore';
import { useAlertStore } from '../stores/alertStore';

function getWsUrl(): string {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
    // Convert http(s) to ws(s)
    return apiUrl.replace(/^http/, 'ws') + '/ws';
}

class WebSocketClient {
    private socket: WebSocket | null = null;
    private reconnectAttempts = 0;
    private maxReconnectAttempts = 5;
    private pingInterval: ReturnType<typeof setInterval> | null = null;

    connect() {
        if (this.socket?.readyState === WebSocket.OPEN) return;

        const token = useAuthStore.getState().jwt;
        if (!token) return;

        const wsUrl = getWsUrl();
        this.socket = new WebSocket(wsUrl);

        this.socket.onopen = () => {
            console.log('WS Connected');
            this.reconnectAttempts = 0;

            // Authenticate by sending JWT as the first message instead of
            // passing it as a query parameter (which is insecure and logged
            // in server access logs).
            if (this.socket?.readyState === WebSocket.OPEN) {
                this.socket.send(JSON.stringify({ type: 'auth', token }));
            }

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
                }
            } catch (e) {
                console.error('WS Parse error', e);
            }
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
        if (this.reconnectAttempts >= this.maxReconnectAttempts) {
            console.log('Max WS reconnects reached');
            return;
        }
        const delay = Math.pow(2, this.reconnectAttempts) * 1000;
        setTimeout(() => this.connect(), delay);
        this.reconnectAttempts++;
    }

    isConnected(): boolean {
        return this.socket?.readyState === WebSocket.OPEN;
    }

    disconnect() {
        if (this.socket) {
            this.socket.close();
            this.socket = null;
        }
        this.stopHeartbeat();
    }
}

export const wsClient = new WebSocketClient();
