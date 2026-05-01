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
    seedRequests: (requests: HITLRequest[]) => void;
    removeRequest: (eventId: string) => void;
    updateStatus: (eventId: string, status: HITLRequest['status']) => void;
}

export const useHITLStore = create<HITLState>((set) => ({
    pendingRequests: [],
    // Used by the WS handler. Skips duplicates so a request that was already
    // seeded via the REST replay endpoint isn't shown twice when the matching
    // pub/sub event arrives a moment later.
    addRequest: (request) => set((state) => {
        if (state.pendingRequests.some(r => r.event_id === request.event_id)) return state;
        return {
            pendingRequests: [request, ...state.pendingRequests].slice(0, 50),
        };
    }),
    // Used by the page-load fetch. Replaces the queue with a fresh snapshot,
    // preserving any in-flight resolved entries the user is still seeing.
    seedRequests: (requests) => set((state) => {
        const incomingIds = new Set(requests.map(r => r.event_id));
        const carryOver = state.pendingRequests.filter(
            r => r.status !== 'PENDING' && !incomingIds.has(r.event_id),
        );
        const seeded: HITLRequest[] = requests.map(r => ({ ...r, status: 'PENDING' }));
        return {
            pendingRequests: [...seeded, ...carryOver].slice(0, 50),
        };
    }),
    removeRequest: (eventId) => set((state) => ({
        pendingRequests: state.pendingRequests.filter(r => r.event_id !== eventId),
    })),
    updateStatus: (eventId, status) => set((state) => ({
        pendingRequests: state.pendingRequests.map(r =>
            r.event_id === eventId ? { ...r, status } : r
        ),
    })),
}));
