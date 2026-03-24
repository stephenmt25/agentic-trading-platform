import { create } from 'zustand';

export interface HITLRequest {
    event_id: string;
    profile_id: string;
    symbol: string;
    side: string;
    quantity: number;
    price: number;
    confidence: number;
    trigger_reason: string;
    agent_scores: Record<string, { score: number; confidence?: number }>;
    risk_metrics: {
        allocation_pct: number;
        drawdown_pct: number;
        regime: string;
        rsi: number;
        atr: number;
    };
    timestamp_us: number;
    status: 'PENDING' | 'APPROVED' | 'REJECTED' | 'EXPIRED';
}

interface HITLState {
    pendingRequests: HITLRequest[];
    addRequest: (request: HITLRequest) => void;
    removeRequest: (eventId: string) => void;
    updateStatus: (eventId: string, status: HITLRequest['status']) => void;
}

export const useHITLStore = create<HITLState>((set) => ({
    pendingRequests: [],
    addRequest: (request) => set((state) => ({
        pendingRequests: [request, ...state.pendingRequests].slice(0, 50),
    })),
    removeRequest: (eventId) => set((state) => ({
        pendingRequests: state.pendingRequests.filter(r => r.event_id !== eventId),
    })),
    updateStatus: (eventId, status) => set((state) => ({
        pendingRequests: state.pendingRequests.map(r =>
            r.event_id === eventId ? { ...r, status } : r
        ),
    })),
}));
