import React from 'react';
import { useRealtimePnl } from '../../lib/hooks/useRealtimePnl';
import { Radio, Clock } from 'lucide-react';

interface PnLDisplayProps {
    profileId: string;
}

export const PnLDisplay: React.FC<PnLDisplayProps> = ({ profileId }) => {
    const pnl = useRealtimePnl(profileId);

    if (!pnl) {
        return (
            <div className="border border-dashed border-border p-3 rounded-md">
                <div className="flex items-center gap-2 mb-1">
                    <Radio className="w-3 h-3 text-amber-500/70" />
                    <span className="text-xs font-medium text-amber-500/70 uppercase tracking-wider">Awaiting Live Data</span>
                </div>
                <p className="text-xs text-muted-foreground leading-relaxed">
                    P&L will appear once the paper trading engine begins publishing snapshots.
                </p>
                <div className="flex items-center gap-1.5 mt-2 text-xs text-muted-foreground">
                    <Clock className="w-3 h-3" />
                    <span>Requires active paper trading session</span>
                </div>
            </div>
        );
    }

    const isPositive = pnl.net_post_tax > 0;
    const isZero = pnl.net_post_tax === 0;
    const colorClass = isZero ? 'text-muted-foreground' : isPositive ? 'text-emerald-500' : 'text-red-500';

    return (
        <div className="border border-border p-4 rounded-md">
            <div className="flex justify-between items-center mb-3">
                <h3 className="text-muted-foreground font-medium text-sm">Real-time P&L (Post-Tax)</h3>
                <span className="text-xs text-muted-foreground font-mono" title="US Only at launch">US</span>
            </div>
            <div className="flex flex-col">
                <span className={`text-2xl font-semibold font-mono tabular-nums tracking-tight ${colorClass}`}>
                    {isPositive ? '+' : ''}{isZero ? '' : ''}${(pnl.net_post_tax).toFixed(2)}
                </span>
                <div className="flex flex-wrap gap-x-4 gap-y-1 mt-3 text-xs font-mono tabular-nums text-muted-foreground">
                    <div><span className="text-muted-foreground/70">Gross:</span> ${(pnl.gross_pnl).toFixed(2)}</div>
                    <div><span className="text-muted-foreground/70">Fees:</span> <span className="text-red-500/70">-${(pnl.fees).toFixed(2)}</span></div>
                    <div><span className="text-muted-foreground/70">Tax Est:</span> <span className="text-red-500/70">-${(pnl.tax_estimate).toFixed(2)}</span></div>
                    <div className={isZero ? 'text-muted-foreground' : isPositive ? 'text-emerald-500/80' : 'text-red-500/80'}>
                        <span className="text-muted-foreground/70">ROI:</span> {isPositive ? '+' : ''}{(pnl.pct_return * 100).toFixed(2)}%
                    </div>
                </div>
            </div>
        </div>
    );
};
