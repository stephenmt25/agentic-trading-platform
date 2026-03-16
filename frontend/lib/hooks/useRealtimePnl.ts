import { useEffect } from 'react';
import { usePortfolioStore } from '../stores/portfolioStore';
import { wsClient } from '../ws/client';
import { PnLSnapshot } from '../types';

export function useRealtimePnl(profileId: string): PnLSnapshot | undefined {
    const pnlData = usePortfolioStore((state) => state.pnlData[profileId]);

    useEffect(() => {
        wsClient.connect();
        return () => {
            // Logic for cleanup handled globally in standard SPA
        };
    }, []);

    return pnlData;
}
