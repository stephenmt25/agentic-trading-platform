'use client';

import React from 'react';
import { usePortfolioStore } from '../../lib/stores/portfolioStore';
import { TrendingUp, TrendingDown, DollarSign } from 'lucide-react';

export const PortfolioSummaryCard: React.FC = () => {
    const pnlData = usePortfolioStore(state => state.pnlData);

    // Aggregate PNL
    const totalNet = Object.values(pnlData).reduce((sum, pnl) => sum + pnl.net_post_tax, 0);
    const totalGross = Object.values(pnlData).reduce((sum, pnl) => sum + pnl.gross_pnl, 0);
    const totalFees = Object.values(pnlData).reduce((sum, pnl) => sum + pnl.fees, 0);

    const isPositive = totalNet >= 0;

    return (
        <div className="bg-gradient-to-br from-slate-900 to-slate-800 rounded-xl p-6 border border-slate-700 shadow-2xl relative overflow-hidden">

            {/* Background Graphic */}
            <div className={`absolute -right-16 -top-16 opacity-10 bg-blend-screen scale-150`}>
                {isPositive ? <TrendingUp size={200} className="text-emerald-500" /> : <TrendingDown size={200} className="text-rose-500" />}
            </div>

            <div className="relative z-10 flex flex-col justify-between h-full space-y-8">
                <div>
                    <h2 className="text-indigo-400 font-bold uppercase tracking-widest text-xs flex items-center gap-2 mb-2">
                        <DollarSign size={16} /> Total Portfolio P&L
                    </h2>
                    <div className="flex items-baseline gap-2">
                        <span className={`text-4xl sm:text-5xl font-extrabold tracking-tighter ${isPositive ? 'text-emerald-400' : 'text-rose-500'}`}>
                            {isPositive ? '+' : ''}${(totalNet).toFixed(2)}
                        </span>
                        <span className="text-slate-500 font-mono text-sm">(post-tax)</span>
                    </div>
                </div>

                <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 px-4 py-3 bg-black/30 rounded-lg">

                    <div className="flex flex-col">
                        <span className="text-[10px] uppercase text-slate-500 font-bold">Invested</span>
                        <span className="text-sm font-mono text-slate-300">-$0.00</span> {/* Mock */}
                    </div>

                    <div className="flex flex-col">
                        <span className="text-[10px] uppercase text-slate-500 font-bold">Gross</span>
                        <span className="text-sm font-mono text-slate-300">${(totalGross).toFixed(2)}</span>
                    </div>

                    <div className="flex flex-col">
                        <span className="text-[10px] uppercase text-slate-500 font-bold">Trading Fees</span>
                        <span className="text-sm font-mono text-rose-400/80">-${(totalFees).toFixed(2)}</span>
                    </div>

                    <div className="flex flex-col">
                        <span className="text-[10px] uppercase text-slate-500 font-bold flex items-center gap-1">
                            Tax <span title="US Only Estimated Bracket" className="cursor-help w-3 h-3 bg-indigo-500 text-[8px] flex items-center justify-center rounded-full text-white font-bold">i</span>
                        </span>
                        <span className="text-sm font-mono text-rose-400/80">-${(0).toFixed(2)}</span>
                    </div>

                </div>
            </div>
        </div>
    );
};
