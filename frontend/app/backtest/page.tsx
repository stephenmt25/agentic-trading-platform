'use client';

import React, { useState, useCallback, useRef, useEffect } from 'react';
import { api } from '../../lib/api/client';
import { BacktestResult, SimulatedTrade } from '../../lib/types';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { EquityCurveChart } from '@/components/backtest/EquityCurveChart';
import { TradesTable } from '@/components/backtest/TradesTable';
import { Loader2, Play, BarChart3, TrendingUp, TrendingDown, Target, Percent, Activity, AlertTriangle } from 'lucide-react';

const DEFAULT_RULES = JSON.stringify(
  {
    conditions: [{ indicator: 'rsi', operator: 'LT', value: 30 }],
    logic: 'AND',
    direction: 'BUY',
    base_confidence: 0.85,
  },
  null,
  2
);

export default function BacktestPage() {
  const [symbol, setSymbol] = useState('BTC/USDT');
  const [startDate, setStartDate] = useState('2025-01-01');
  const [endDate, setEndDate] = useState('2025-06-01');
  const [slippage, setSlippage] = useState('0.001');
  const [rulesJson, setRulesJson] = useState(DEFAULT_RULES);
  const [jobId, setJobId] = useState<string | null>(null);
  const [status, setStatus] = useState<'idle' | 'queued' | 'polling' | 'completed' | 'error'>('idle');
  const [result, setResult] = useState<BacktestResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const pollTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const cancelledRef = useRef(false);

  // Cleanup polling on unmount
  useEffect(() => {
    return () => {
      cancelledRef.current = true;
      if (pollTimerRef.current) {
        clearTimeout(pollTimerRef.current);
        pollTimerRef.current = null;
      }
    };
  }, []);

  const pollResult = useCallback(
    async (id: string) => {
      setStatus('polling');
      cancelledRef.current = false;
      let attempts = 0;
      const maxAttempts = 60;

      const poll = async () => {
        if (cancelledRef.current) return;
        try {
          const res = await api.backtest.result(id);
          if (cancelledRef.current) return;

          if (res.status === 'completed') {
            setResult(res as unknown as BacktestResult);
            setStatus('completed');
            return;
          }
          if (res.status === 'running' || res.status === 'queued') {
            attempts++;
            if (attempts < maxAttempts) {
              pollTimerRef.current = setTimeout(poll, 2000);
            } else {
              setError('Backtest timed out');
              setStatus('error');
            }
            return;
          }
          setError(`Unknown status: ${res.status}`);
          setStatus('error');
        } catch (e: unknown) {
          if (cancelledRef.current) return;
          setError(e instanceof Error ? e.message : 'Failed to fetch result');
          setStatus('error');
        }
      };
      poll();
    },
    []
  );

  const handleSubmit = async () => {
    setError(null);
    setResult(null);

    let parsed;
    try {
      parsed = JSON.parse(rulesJson);
    } catch {
      setError('Invalid JSON in strategy rules');
      return;
    }

    try {
      setStatus('queued');
      const res = await api.backtest.submit({
        symbol,
        strategy_rules: parsed,
        start_date: `${startDate}T00:00:00`,
        end_date: `${endDate}T00:00:00`,
        slippage_pct: parseFloat(slippage),
      });
      setJobId(res.job_id);
      pollResult(res.job_id);
    } catch (e: any) {
      setError(e.message || 'Failed to submit backtest');
      setStatus('error');
    }
  };

  const isRunning = status === 'queued' || status === 'polling';

  return (
    <div className="flex flex-col gap-6 h-full">
      <h1 className="text-xl font-semibold tracking-tight text-foreground border-b border-border pb-4">
        Backtest Engine
      </h1>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        {/* Left: Configuration */}
        <section className="xl:col-span-1 space-y-4">
          <h2 className="uppercase text-xs font-semibold text-muted-foreground tracking-wider">
            Configuration
          </h2>
          <div>
            <label className="text-xs uppercase text-muted-foreground font-medium tracking-wider block mb-1.5">
              Symbol
            </label>
            <Input
              value={symbol}
              onChange={(e) => setSymbol(e.target.value)}
              className="font-mono tabular-nums bg-background border-border min-h-[44px]"
              placeholder="BTC/USDT"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs uppercase text-muted-foreground font-medium tracking-wider block mb-1.5">
                Start Date
              </label>
              <Input
                type="date"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
                className="font-mono tabular-nums bg-background border-border min-h-[44px]"
              />
            </div>
            <div>
              <label className="text-xs uppercase text-muted-foreground font-medium tracking-wider block mb-1.5">
                End Date
              </label>
              <Input
                type="date"
                value={endDate}
                onChange={(e) => setEndDate(e.target.value)}
                className="font-mono tabular-nums bg-background border-border min-h-[44px]"
              />
            </div>
          </div>

          <div>
            <label className="text-xs uppercase text-muted-foreground font-medium tracking-wider block mb-1.5">
              Slippage %
            </label>
            <Input
              value={slippage}
              onChange={(e) => setSlippage(e.target.value)}
              className="font-mono tabular-nums bg-background border-border min-h-[44px]"
              placeholder="0.001"
              type="number"
              step="0.0001"
            />
          </div>

          <div>
            <label className="text-xs uppercase text-muted-foreground font-medium tracking-wider block mb-1.5">
              Strategy Rules (JSON)
            </label>
            <textarea
              value={rulesJson}
              onChange={(e) => setRulesJson(e.target.value)}
              className="w-full h-40 font-mono tabular-nums text-sm bg-background border border-border rounded-md p-3 text-foreground/80 resize-none focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
              spellCheck={false}
            />
          </div>

          <Button
            onClick={handleSubmit}
            disabled={isRunning}
            className="w-full font-medium min-h-[44px]"
          >
            {isRunning ? (
              <>
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                {status === 'queued' ? 'Queued...' : 'Running...'}
              </>
            ) : (
              <>
                <Play className="w-4 h-4 mr-2" />
                Run Backtest
              </>
            )}
          </Button>

          {error && (
            <div className="text-sm text-red-500 border border-destructive/30 rounded-md p-3 font-mono flex items-start gap-2">
              <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
              <span>{error}</span>
            </div>
          )}

          {jobId && (
            <div className="text-xs text-muted-foreground font-mono tabular-nums">
              Job ID: {jobId}
            </div>
          )}
        </section>

        {/* Right: Results */}
        <div className="xl:col-span-2 flex flex-col gap-6">
          {result ? (
            <>
              {/* Metrics Grid */}
              <div className="grid grid-cols-2 lg:grid-cols-3 gap-3">
                <MetricCard
                  label="Total Trades"
                  value={result.total_trades.toString()}
                  icon={<BarChart3 className="w-4 h-4" />}
                />
                <MetricCard
                  label="Win Rate"
                  value={`${(result.win_rate * 100).toFixed(1)}%`}
                  icon={<Target className="w-4 h-4" />}
                  color={result.win_rate >= 0.5 ? 'emerald' : 'rose'}
                />
                <MetricCard
                  label="Avg Return"
                  value={`${(result.avg_return * 100).toFixed(2)}%`}
                  icon={result.avg_return >= 0 ? <TrendingUp className="w-4 h-4" /> : <TrendingDown className="w-4 h-4" />}
                  color={result.avg_return >= 0 ? 'emerald' : 'rose'}
                />
                <MetricCard
                  label="Max Drawdown"
                  value={`${(result.max_drawdown * 100).toFixed(2)}%`}
                  icon={<TrendingDown className="w-4 h-4" />}
                  color="rose"
                />
                <MetricCard
                  label="Sharpe Ratio"
                  value={result.sharpe.toFixed(2)}
                  icon={<Activity className="w-4 h-4" />}
                  color={result.sharpe >= 1 ? 'emerald' : result.sharpe >= 0 ? 'amber' : 'rose'}
                />
                <MetricCard
                  label="Profit Factor"
                  value={result.profit_factor === Infinity ? 'INF' : result.profit_factor.toFixed(2)}
                  icon={<Percent className="w-4 h-4" />}
                  color={result.profit_factor >= 1.5 ? 'emerald' : result.profit_factor >= 1 ? 'amber' : 'rose'}
                />
              </div>

              {/* Equity Curve */}
              {result.equity_curve && result.equity_curve.length > 0 && (
                <section className="border-t border-border pt-4">
                  <h2 className="uppercase text-xs font-semibold text-muted-foreground tracking-wider mb-4">
                    Equity Curve
                  </h2>
                  <EquityCurveChart data={result.equity_curve} />
                </section>
              )}

              {/* Trades Table */}
              {result.trades && result.trades.length > 0 && (
                <section className="border-t border-border pt-4">
                  <h2 className="uppercase text-xs font-semibold text-muted-foreground tracking-wider mb-4">
                    Simulated Trades ({result.trades.length})
                  </h2>
                  <TradesTable trades={result.trades} />
                </section>
              )}
            </>
          ) : (
            <div className="flex-1 flex flex-col items-center justify-center gap-3 py-16">
              <p className="text-sm text-muted-foreground">
                {isRunning ? 'Running simulation...' : 'Configure and run a backtest to see results'}
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function MetricCard({
  label,
  value,
  icon,
  color = 'neutral',
}: {
  label: string;
  value: string;
  icon: React.ReactNode;
  color?: string;
}) {
  const colorMap: Record<string, string> = {
    emerald: 'text-emerald-500',
    rose: 'text-red-500',
    amber: 'text-amber-500',
    neutral: 'text-foreground',
  };

  return (
    <div className="border border-border rounded-md p-4">
      <div className="flex items-center gap-2 mb-2">
        <span className="text-muted-foreground">{icon}</span>
        <span className="text-xs uppercase text-muted-foreground font-medium tracking-wider">
          {label}
        </span>
      </div>
      <span className={`text-2xl font-mono tabular-nums font-semibold ${colorMap[color] || colorMap.neutral}`}>
        {value}
      </span>
    </div>
  );
}
