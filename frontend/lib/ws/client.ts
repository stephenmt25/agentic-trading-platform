import { useAuthStore } from '../stores/authStore';
import { usePortfolioStore } from '../stores/portfolioStore';
import { useAlertStore } from '../stores/alertStore';

const WS_URL = 'ws://localhost:8000/ws';

class WebSocketClient {
    private socket: WebSocket | null = null;
    private reconnectAttempts = 0;
    private maxReconnectAttempts = 5;
    private pingInterval: any;

    connect() {
        if (this.socket?.readyState === WebSocket.OPEN) return;

        const token = useAuthStore.getState().jwt;
        if (!token) return;

        this.socket = new WebSocket(`${WS_URL}?token=${token}`);

        this.socket.onopen = () => {
            console.log('WS Connected');
            this.reconnectAttempts = 0;
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
        if (this.pingInterval) clearInterval(this.pingInterval);
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

    disconnect() {
        if (this.socket) {
            this.socket.close();
            this.socket = null;
        }
        this.stopHeartbeat();
    }
}

export const wsClient = new WebSocketClient();
