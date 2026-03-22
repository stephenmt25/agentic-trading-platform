import React from 'react';
import { Regime } from '../../lib/types';
import { TrendingUp, TrendingDown, Minus, AlertTriangle, Skull } from 'lucide-react';

interface RegimeBadgeProps {
    regime: Regime;
}

export const RegimeBadge: React.FC<RegimeBadgeProps> = ({ regime }) => {
    let config = { icon: <Minus size={14} />, color: 'text-muted-foreground border-border', label: 'RANGING' };

    switch (regime) {
        case 'TRENDING_UP':
            config = { icon: <TrendingUp size={14} />, color: 'text-emerald-500 border-emerald-500/30', label: 'UPTREND' };
            break;
        case 'TRENDING_DOWN':
            config = { icon: <TrendingDown size={14} />, color: 'text-red-500 border-red-500/30', label: 'DOWNTREND' };
            break;
        case 'HIGH_VOLATILITY':
            config = { icon: <AlertTriangle size={14} />, color: 'text-amber-500 border-amber-500/30', label: 'HIGH VOL' };
            break;
        case 'CRISIS':
            config = { icon: <Skull size={14} />, color: 'text-red-500 border-red-500/40', label: 'CRISIS' };
            break;
    }

    return (
        <div
            className={`px-2 py-1 flex items-center space-x-1.5 rounded-md text-xs font-medium font-mono tracking-wider border ${config.color}`}
            title={`Current Market Regime: ${regime}`}
        >
            {config.icon}
            <span>{config.label}</span>
        </div>
    );
};
