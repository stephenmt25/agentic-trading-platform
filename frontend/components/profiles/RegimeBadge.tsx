import React from 'react';
import { Regime } from '../../lib/types';
import { TrendingUp, TrendingDown, Minus, AlertTriangle, Skull } from 'lucide-react';

interface RegimeBadgeProps {
    regime: Regime;
}

export const RegimeBadge: React.FC<RegimeBadgeProps> = ({ regime }) => {
    let config = { icon: <Minus size={14} />, color: 'bg-slate-700 text-slate-300', label: 'RANGING' };

    switch (regime) {
        case 'TRENDING_UP':
            config = { icon: <TrendingUp size={14} />, color: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30', label: 'UPTREND' };
            break;
        case 'TRENDING_DOWN':
            config = { icon: <TrendingDown size={14} />, color: 'bg-rose-500/20 text-rose-400 border-rose-500/30', label: 'DOWNTREND' };
            break;
        case 'HIGH_VOLATILITY':
            config = { icon: <AlertTriangle size={14} />, color: 'bg-amber-500/20 text-amber-400 border-amber-500/30', label: 'HIGH VOL' };
            break;
        case 'CRISIS':
            config = { icon: <Skull size={14} />, color: 'bg-red-600/20 text-red-500 border-red-600/50 animate-pulse', label: 'CRISIS' };
            break;
    }

    return (
        <div
            className={`px-3 py-1 flex items-center space-x-2 rounded-full text-xs font-bold font-mono tracking-wider border ${config.color}`}
            title={`Current Market Regime: ${regime}`}
        >
            {config.icon}
            <span>{config.label}</span>
        </div>
    );
};
