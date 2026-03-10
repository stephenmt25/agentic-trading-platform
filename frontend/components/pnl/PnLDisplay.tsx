import React from 'react';
import { useRealtimePnl } from '../../lib/hooks/useRealtimePnl';

interface PnLDisplayProps {
    profileId: string;
}

export const PnLDisplay: React.FC<PnLDisplayProps> = ({ profileId }) => {
    const pnl = useRealtimePnl(profileId);

    if (!pnl) {
        return <div className="animate-pulse flex space-x-4 bg-slate-800 h-16 w-full rounded"></div>;
    }

    const isPositive = pnl.net_post_tax >= 0;
    const colorClass = isPositive ? 'text-emerald-400' : 'text-rose-500';

    return (
        <div className="bg-slate-900 border border-slate-700/50 p-6 rounded-xl shadow-lg transform transition-all duration-300 hover:scale-[1.02]">
            <div className="flex justify-between items-center mb-4">
                <h3 className="text-slate-400 font-medium text-sm">Real-time P&L (Post-Tax)</h3>
                <span className="text-xs text-slate-500 font-mono" title="US Only at launch">US</span>
            </div>
            <div className="flex flex-col">
                <span className={`text-4xl font-bold font-mono tracking-tight ${colorClass}`}>
                    {isPositive ? '+' : ''}${(pnl.net_post_tax).toFixed(2)}
                </span>
                <div className="flex space-x-4 mt-4 text-xs font-mono text-slate-500">
                    <div><span className="text-slate-400">Gross:</span> ${(pnl.gross_pnl).toFixed(2)}</div>
                    <div><span className="text-slate-400">Fees:</span> ${(pnl.fees).toFixed(2)}</div>
                    <div><span className="text-slate-400">Tax Est:</span> ${(pnl.tax_estimate).toFixed(2)}</div>
                    <div className={isPositive ? 'text-emerald-500/80' : 'text-rose-500/80'}>
                        <span className="text-slate-400">ROI:</span> {(pnl.pct_return * 100).toFixed(2)}%
                    </div>
                </div>
            </div>
        </div>
    );
};
