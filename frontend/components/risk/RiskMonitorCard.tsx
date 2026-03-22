'use client';

import React, { useEffect, useState } from 'react';
import { api } from '../../lib/api/client';
import { RiskStatus } from '../../lib/types';
import { Badge } from '@/components/ui/badge';
import {
  AlertTriangle,
  TrendingDown,
  BarChart3,
  RefreshCw,
  ShieldAlert,
} from 'lucide-react';

const POLL_INTERVAL = 10000; // 10 seconds
const DEFAULT_CB_THRESHOLD = 0.02; // 2% default circuit breaker
const DEFAULT_DD_THRESHOLD = 0.10; // 10% default drawdown limit
const DEFAULT_ALLOC_LIMIT = 0.25; // 25% default allocation limit

interface RiskMonitorCardProps {
  profileIds?: string[];
}

export const RiskMonitorCard: React.FC<RiskMonitorCardProps> = ({ profileIds }) => {
  const [riskData, setRiskData] = useState<RiskStatus[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  const fetchRisk = async () => {
    try {
      if (profileIds && profileIds.length > 0) {
        const results = await Promise.all(
          profileIds.map((pid) => api.agents.risk(pid))
        );
        setRiskData(results as RiskStatus[]);
      } else {
        const results = await api.agents.allRisk();
        setRiskData(results as RiskStatus[]);
      }
      setError(false);
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchRisk();
    const interval = setInterval(fetchRisk, POLL_INTERVAL);
    return () => clearInterval(interval);
  }, [profileIds?.join(',')]);

  const hasAnyData = riskData.length > 0;

  return (
    <section>
      <div className="flex items-center justify-between mb-4">
        <h2 className="uppercase text-xs font-semibold text-muted-foreground tracking-wider flex items-center gap-2">
          Risk Monitor
        </h2>
        <button
          onClick={fetchRisk}
          className="p-2 rounded-md hover:bg-accent transition-colors min-h-[44px] min-w-[44px] flex items-center justify-center focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
          aria-label="Refresh risk data"
        >
          <RefreshCw className={`w-3.5 h-3.5 text-muted-foreground ${loading ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {error ? (
        <div className="flex flex-col items-center gap-2 py-6 text-center">
          <ShieldAlert className="w-5 h-5 text-muted-foreground/50" />
          <p className="text-xs text-muted-foreground">Risk API unavailable</p>
        </div>
      ) : !hasAnyData ? (
        <div className="flex flex-col items-center gap-2 py-6 text-center">
          <p className="text-xs text-muted-foreground font-mono">ALL CLEAR</p>
          <p className="text-xs text-muted-foreground/70">
            No active risk data. Metrics appear after trading activity.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {riskData.map((risk) => {
              const cbThreshold = risk.circuit_breaker_threshold || DEFAULT_CB_THRESHOLD;
              const dailyLoss = -risk.daily_pnl_pct;
              const cbPct = Math.min(100, (dailyLoss / cbThreshold) * 100);
              const cbTripped = dailyLoss >= cbThreshold;

              const ddPct = Math.min(100, (risk.drawdown_pct / DEFAULT_DD_THRESHOLD) * 100);
              const ddDanger = risk.drawdown_pct > DEFAULT_DD_THRESHOLD * 0.5;

              const allocPct = Math.min(100, (risk.allocation_pct / DEFAULT_ALLOC_LIMIT) * 100);

              return (
                <div
                  key={risk.profile_id}
                  className={`p-3 rounded-md border space-y-3 ${
                    cbTripped
                      ? 'border-red-500/40'
                      : 'border-border'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-mono tabular-nums text-muted-foreground truncate max-w-[180px]">
                      {risk.profile_id.slice(0, 12)}...
                    </span>
                    {cbTripped && (
                      <Badge variant="outline" className="text-red-500 border-red-500/30 text-xs font-medium">
                        CIRCUIT BREAKER
                      </Badge>
                    )}
                  </div>

                  {/* Daily P&L vs Circuit Breaker */}
                  <RiskBar
                    label="Daily P&L vs Breaker"
                    icon={<AlertTriangle className="w-3 h-3" />}
                    current={dailyLoss}
                    limit={cbThreshold}
                    pct={cbPct}
                    format={(v) => `-${(v * 100).toFixed(2)}%`}
                    limitFormat={(v) => `${(v * 100).toFixed(1)}%`}
                    danger={cbTripped}
                    warning={cbPct > 50}
                  />

                  {/* Drawdown */}
                  <RiskBar
                    label="Current Drawdown"
                    icon={<TrendingDown className="w-3 h-3" />}
                    current={risk.drawdown_pct}
                    limit={DEFAULT_DD_THRESHOLD}
                    pct={ddPct}
                    format={(v) => `${(v * 100).toFixed(2)}%`}
                    limitFormat={(v) => `${(v * 100).toFixed(0)}%`}
                    danger={risk.drawdown_pct > DEFAULT_DD_THRESHOLD}
                    warning={ddDanger}
                  />

                  {/* Allocation */}
                  <RiskBar
                    label="Allocation Used"
                    icon={<BarChart3 className="w-3 h-3" />}
                    current={risk.allocation_pct}
                    limit={DEFAULT_ALLOC_LIMIT}
                    pct={allocPct}
                    format={(v) => `${(v * 100).toFixed(1)}%`}
                    limitFormat={(v) => `${(v * 100).toFixed(0)}%`}
                    danger={risk.allocation_pct >= DEFAULT_ALLOC_LIMIT}
                    warning={allocPct > 75}
                  />
                </div>
              );
            })}
          </div>
        )}
    </section>
  );
};

function RiskBar({
  label,
  icon,
  current,
  limit,
  pct,
  format,
  limitFormat,
  danger,
  warning,
}: {
  label: string;
  icon: React.ReactNode;
  current: number;
  limit: number;
  pct: number;
  format: (v: number) => string;
  limitFormat: (v: number) => string;
  danger: boolean;
  warning: boolean;
}) {
  const barColor = danger
    ? 'bg-red-500'
    : warning
    ? 'bg-amber-500'
    : 'bg-emerald-500';

  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-1.5">
          <span className={danger ? 'text-red-500' : 'text-muted-foreground'}>
            {icon}
          </span>
          <span className="text-xs uppercase font-medium tracking-wider text-muted-foreground">
            {label}
          </span>
        </div>
        <div className="flex items-center gap-2 text-xs font-mono tabular-nums">
          <span className={danger ? 'text-red-500 font-medium' : warning ? 'text-amber-500' : 'text-muted-foreground'}>
            {format(current)}
          </span>
          <span className="text-muted-foreground/50">/</span>
          <span className="text-muted-foreground/70">{limitFormat(limit)}</span>
        </div>
      </div>
      <div className="h-1.5 bg-accent rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-[width] duration-700 ${barColor}`}
          style={{ width: `${Math.max(0, Math.min(100, pct))}%` }}
        />
      </div>
    </div>
  );
}
