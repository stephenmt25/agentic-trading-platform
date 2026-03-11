'use client';

import React from 'react';
import { usePortfolioStore } from '../../lib/stores/portfolioStore';
import { TrendingUp, TrendingDown, DollarSign } from 'lucide-react';

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export const PortfolioSummaryCard: React.FC = () => {
    const pnlData = usePortfolioStore(state => state.pnlData);

    const totalNet = Object.values(pnlData).reduce((sum, pnl) => sum + pnl.net_post_tax, 0);
    const totalGross = Object.values(pnlData).reduce((sum, pnl) => sum + pnl.gross_pnl, 0);
    const totalFees = Object.values(pnlData).reduce((sum, pnl) => sum + pnl.fees, 0);

    const isPositive = totalNet >= 0;

    return (
        <Card className="relative overflow-hidden border-border bg-card shadow-2xl group">
            <div className="absolute inset-0 bg-gradient-to-br from-primary/10 via-transparent to-transparent opacity-50 group-hover:opacity-100 transition-opacity duration-500" />
            <div className={`absolute -right-16 -top-16 opacity-[0.03] bg-blend-screen scale-150 pointer-events-none transition-transform duration-700 group-hover:scale-[1.6]`}>
                {isPositive ? <TrendingUp size={200} className="text-emerald-500" /> : <TrendingDown size={200} className="text-rose-500" />}
            </div>

            <CardHeader className="relative z-10 pb-2">
                <CardTitle className="text-primary font-bold uppercase tracking-widest text-xs flex items-center gap-2">
                    <DollarSign size={16} /> Total Portfolio P&L
                </CardTitle>
            </CardHeader>

            <CardContent className="relative z-10 space-y-8">
                <div className="flex items-baseline gap-2">
                    <span className={`text-5xl lg:text-6xl font-mono font-bold tracking-tighter ${isPositive ? 'text-emerald-400 drop-shadow-[0_0_15px_rgba(52,211,153,0.3)]' : 'text-rose-500 drop-shadow-[0_0_15px_rgba(244,63,94,0.3)]'}`}>
                        {isPositive ? '+' : ''}${(totalNet).toFixed(2)}
                    </span>
                    <span className="text-muted-foreground font-mono text-sm font-medium">(post-tax)</span>
                </div>

                <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 p-4 bg-black/40 backdrop-blur-md rounded-xl border border-white/5">
                    <div className="flex flex-col space-y-1">
                        <span className="text-[10px] uppercase text-muted-foreground font-bold tracking-wider">Invested</span>
                        <span className="text-sm font-mono text-slate-300 font-medium">$0.00</span>
                    </div>
                    <div className="flex flex-col space-y-1">
                        <span className="text-[10px] uppercase text-muted-foreground font-bold tracking-wider">Gross P&L</span>
                        <span className="text-sm font-mono text-slate-300 font-medium">${(totalGross).toFixed(2)}</span>
                    </div>
                    <div className="flex flex-col space-y-1">
                        <span className="text-[10px] uppercase text-muted-foreground font-bold tracking-wider">Trading Fees</span>
                        <span className="text-sm font-mono text-rose-400/90 font-medium">-${(totalFees).toFixed(2)}</span>
                    </div>
                    <div className="flex flex-col space-y-1">
                        <span className="text-[10px] uppercase text-muted-foreground font-bold tracking-wider flex items-center gap-1">
                            Tax Est. <span className="cursor-help w-3 h-3 bg-primary/20 text-primary text-[8px] flex items-center justify-center rounded-full font-bold">i</span>
                        </span>
                        <span className="text-sm font-mono text-rose-400/90 font-medium">-${(0).toFixed(2)}</span>
                    </div>
                </div>
            </CardContent>
        </Card>
    );
};
