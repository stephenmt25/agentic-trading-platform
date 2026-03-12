'use client';

import React, { useEffect, useState } from 'react';
import { api } from '../../lib/api/client';
import { RiskStatus } from '../../lib/types';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import {
  Shield,
  AlertTriangle,
  TrendingDown,
  BarChart3,
  RefreshCw,
  ShieldAlert,
  ShieldCheck,
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
    <Card className="border-border bg-card shadow-2xl">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="uppercase text-xs font-bold text-muted-foreground tracking-wider flex items-center gap-2">
            <Shield className="w-3.5 h-3.5" />
            Risk Monitor
          </CardTitle>
          <button
            onClick={fetchRisk}
            className="p-1 rounded hover:bg-white/5 transition-colors"
            title="Refresh"
          >
            <RefreshCw className={`w-3 h-3 text-muted-foreground ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </CardHeader>
      <CardContent>
        {error ? (
          <div className="flex flex-col items-center gap-2 py-6 text-center">
            <ShieldAlert className="w-5 h-5 text-muted-foreground/50" />
            <p className="text-xs text-muted-foreground">Risk API unavailable</p>
          </div>
        ) : !hasAnyData ? (
          <div className="flex flex-col items-center gap-2 py-6 text-center">
            <ShieldCheck className="w-5 h-5 text-emerald-500/30" />
            <p className="text-xs text-muted-foreground font-mono">ALL CLEAR</p>
            <p className="text-[10px] text-muted-foreground/70">
              No active risk data. Metrics appear after trading activity.
            </p>
          </div>
        ) : (
          <div className="space-y-4">
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
                  className={`p-4 rounded-lg border space-y-3 ${
                    cbTripped
                      ? 'bg-rose-950/20 border-rose-500/50'
                      : 'bg-black/20 border-border/50'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-mono text-muted-foreground truncate max-w-[180px]">
                      {risk.profile_id.slice(0, 12)}...
                    </span>
                    {cbTripped && (
                      <Badge className="bg-rose-500/20 text-rose-400 text-[9px] font-bold animate-pulse">
                        CIRCUIT BREAKER TRIPPED
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
      </CardContent>
    </Card>
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
    ? 'bg-rose-500'
    : warning
    ? 'bg-amber-500'
    : 'bg-emerald-500';

  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-1.5">
          <span className={danger ? 'text-rose-400' : 'text-muted-foreground'}>
            {icon}
          </span>
          <span className="text-[9px] uppercase font-bold tracking-wider text-muted-foreground">
            {label}
          </span>
        </div>
        <div className="flex items-center gap-2 text-[10px] font-mono">
          <span className={danger ? 'text-rose-400 font-bold' : warning ? 'text-amber-400' : 'text-slate-400'}>
            {format(current)}
          </span>
          <span className="text-muted-foreground/50">/</span>
          <span className="text-muted-foreground/70">{limitFormat(limit)}</span>
        </div>
      </div>
      <div className="h-1.5 bg-slate-800 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-700 ${barColor}`}
          style={{ width: `${Math.max(0, Math.min(100, pct))}%` }}
        />
      </div>
    </div>
  );
}
