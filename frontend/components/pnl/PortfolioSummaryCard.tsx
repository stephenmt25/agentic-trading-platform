'use client';

import React from 'react';
import { usePortfolioStore } from '../../lib/stores/portfolioStore';

export const PortfolioSummaryCard: React.FC = () => {
    const pnlData = usePortfolioStore(state => state.pnlData);

    const entries = Object.values(pnlData);
    const totalNet = entries.reduce((sum, pnl) => sum + pnl.net_post_tax, 0);
    const totalGross = entries.reduce((sum, pnl) => sum + pnl.gross_pnl, 0);
    const totalFees = entries.reduce((sum, pnl) => sum + pnl.fees, 0);
    const totalTaxEst = entries.reduce((sum, pnl) => sum + pnl.tax_estimate, 0);
    // Invested = gross PnL minus net post-tax (captures fees + taxes deducted from principal)
    // When no positions exist this shows $0.00 which is correct.
    const totalInvested = totalGross - totalNet + totalFees + totalTaxEst;

    const isPositive = totalNet > 0;
    const isZero = totalNet === 0;
    const netColor = isZero ? 'text-muted-foreground' : isPositive ? 'text-emerald-500' : 'text-red-500';

    return (
        <section>
            <h2 className="uppercase text-xs font-semibold text-muted-foreground tracking-wider mb-4">
                Total Portfolio P&L
            </h2>

            <div className="space-y-6">
                <div className="flex items-baseline gap-2">
                    <span className={`text-2xl md:text-4xl font-mono tabular-nums font-semibold tracking-tight ${netColor}`}>
                        {isPositive ? '+' : ''}${(totalNet).toFixed(2)}
                    </span>
                    <span className="text-muted-foreground font-mono text-sm">(post-tax)</span>
                </div>

                <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 pt-4 border-t border-border">
                    <div className="flex flex-col space-y-1">
                        <span className="text-xs uppercase text-muted-foreground font-medium tracking-wider">Invested</span>
                        <span className="text-sm font-mono tabular-nums text-foreground">${totalInvested.toFixed(2)}</span>
                    </div>
                    <div className="flex flex-col space-y-1">
                        <span className="text-xs uppercase text-muted-foreground font-medium tracking-wider">Gross P&L</span>
                        <span className="text-sm font-mono tabular-nums text-foreground">${(totalGross).toFixed(2)}</span>
                    </div>
                    <div className="flex flex-col space-y-1">
                        <span className="text-xs uppercase text-muted-foreground font-medium tracking-wider">Trading Fees</span>
                        <span className="text-sm font-mono tabular-nums text-red-500/80">-${(totalFees).toFixed(2)}</span>
                    </div>
                    <div className="flex flex-col space-y-1">
                        <span className="text-xs uppercase text-muted-foreground font-medium tracking-wider">
                            Tax Est.
                        </span>
                        <span className="text-sm font-mono tabular-nums text-red-500/80">-${totalTaxEst.toFixed(2)}</span>
                    </div>
                </div>
            </div>
        </section>
    );
};
