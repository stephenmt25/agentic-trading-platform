import { useEffect, useMemo } from 'react';
import { usePortfolioStore, PnLPositionSnapshot } from '../stores/portfolioStore';
import { wsClient } from '../ws/client';

// Per-profile aggregate over the per-position snapshots in the store
// (FE-W2: pnlData is keyed by position_id; a profile may hold many).
export interface ProfilePnLSummary {
    profile_id: string;
    position_count: number;
    gross_pnl: number;
    fees: number;
    net_pre_tax: number;
    net_post_tax: number;
    tax_estimate: number;
    /** Pass-through when the profile has exactly one position; null
     * otherwise — per-position returns cannot be summed without
     * cost-basis weights, which the wire does not carry. */
    pct_return: number | null;
    timestamp_us: number;
}

export function useRealtimePnl(profileId: string): ProfilePnLSummary | undefined {
    const pnlData = usePortfolioStore((state) => state.pnlData);

    useEffect(() => {
        wsClient.connect();
        return () => {
            // Logic for cleanup handled globally in standard SPA
        };
    }, []);

    return useMemo(() => {
        const snapshots = Object.values(pnlData).filter(
            (s) => s.profile_id === profileId
        );
        if (snapshots.length === 0) return undefined;
        const sum = (pick: (s: PnLPositionSnapshot) => number | null) =>
            snapshots.reduce((acc, s) => acc + (pick(s) ?? 0), 0);
        return {
            profile_id: profileId,
            position_count: snapshots.length,
            gross_pnl: sum((s) => s.gross_pnl),
            fees: sum((s) => s.fees),
            net_pre_tax: sum((s) => s.net_pre_tax),
            net_post_tax: sum((s) => s.net_post_tax),
            tax_estimate: sum((s) => s.tax_estimate),
            pct_return: snapshots.length === 1 ? snapshots[0].pct_return : null,
            timestamp_us: Math.max(...snapshots.map((s) => s.timestamp_us)),
        };
    }, [pnlData, profileId]);
}
