import { create } from 'zustand';
import { Profile } from '../types';

// FE-W2 shared contract — the WS client (producer) and every pnlData
// consumer code to this exact shape. Decimal fields arrive str-encoded on
// the wire (registry row 54) and are parsed to number; missing/unparseable
// values are null and must be null-guarded by consumers.
export interface PnLPositionSnapshot {
    position_id: string;
    profile_id: string;
    symbol: string;
    gross_pnl: number | null;
    fees: number | null;
    net_pre_tax: number | null;
    net_post_tax: number | null;
    tax_estimate: number | null;
    pct_return: number | null;
    timestamp_us: number;
}

interface PortfolioState {
    profiles: Profile[];
    activeProfileId: string | null;
    // Keyed by position_id — PNL_UPDATE events are per-position. (Was keyed
    // by profile_id: last-write-wins dropped every position but one, so
    // total-PnL sums were wrong whenever a profile held >1 position.)
    pnlData: Record<string, PnLPositionSnapshot>;
    setProfiles: (profiles: Profile[]) => void;
    setActiveProfileId: (id: string | null) => void;
    // Batched: ONE zustand set() per flush. The WS client buffers
    // latest-per-position and flushes at most every 250ms — one store write
    // (and one render pass) per flush instead of one per message.
    applyPnlSnapshots: (snapshots: PnLPositionSnapshot[]) => void;
}

export const usePortfolioStore = create<PortfolioState>((set) => ({
    profiles: [],
    activeProfileId: null,
    pnlData: {},
    setProfiles: (profiles) => set({ profiles }),
    setActiveProfileId: (id) => set({ activeProfileId: id }),
    applyPnlSnapshots: (snapshots) => {
        if (snapshots.length === 0) return;
        set((state) => {
            const next = { ...state.pnlData };
            for (const snapshot of snapshots) {
                next[snapshot.position_id] = snapshot;
            }
            return { pnlData: next };
        });
    },
}));
