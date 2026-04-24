'use client';

import React, { useState, useCallback, useRef, useEffect } from 'react';
import { api } from '../../lib/api/client';
import { BacktestResult, SimulatedTrade } from '../../lib/types';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { EquityCurveChart } from '@/components/backtest/EquityCurveChart';
import { TradesTable } from '@/components/backtest/TradesTable';
import { Loader2, Play, BarChart3, TrendingUp, TrendingDown, Target, Percent, Activity, AlertTriangle } from 'lucide-react';
import { motion } from "framer-motion";
import { pageEnter } from "@/lib/motion";

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

// The sequential simulator runs per-candle with Decimal math; multi-month
// 1m-timeframe runs can take several minutes. The old 2-min cap timed out
// constantly even when the backend was still churning successfully.
const POLL_INTERVAL_MS = 2000;
const POLL_TIMEOUT_MS = 10 * 60 * 1000;

function formatElapsed(ms: number): string {
  const total = Math.max(0, Math.floor(ms / 1000));
  const m = Math.floor(total / 60);
  const s = total % 60;
  return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
}

type BackendJobStatus = 'queued' | 'running' | 'completed' | 'failed';

export default function BacktestPage() {
  const [symbol, setSymbol] = useState('BTC/USDT');
  const [startDate, setStartDate] = useState('2025-01-01');
  const [endDate, setEndDate] = useState('2025-06-01');
  const [slippage, setSlippage] = useState('0.001');
  const [rulesJson, setRulesJson] = useState(DEFAULT_RULES);
  const [jobId, setJobId] = useState<string | null>(null);
  const [status, setStatus] = useState<'idle' | 'queued' | 'polling' | 'completed' | 'error'>('idle');
  const [jobStatus, setJobStatus] = useState<BackendJobStatus | null>(null);
  const [result, setResult] = useState<BacktestResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [runConfig, setRunConfig] = useState<{ symbol: string; start: string; end: string; slippage: string } | null>(null);
  const [elapsedMs, setElapsedMs] = useState(0);
  const pollTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const elapsedTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const startTimeRef = useRef<number>(0);
  const cancelledRef = useRef(false);

  const stopElapsedTimer = useCallback(() => {
    if (elapsedTimerRef.current) {
      clearInterval(elapsedTimerRef.current);
      elapsedTimerRef.current = null;
    }
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      cancelledRef.current = true;
      if (pollTimerRef.current) {
        clearTimeout(pollTimerRef.current);
        pollTimerRef.current = null;
      }
      stopElapsedTimer();
    };
  }, [stopElapsedTimer]);

  const pollResult = useCallback(
    async (id: string) => {
      setStatus('polling');
      cancelledRef.current = false;
      const deadline = Date.now() + POLL_TIMEOUT_MS;

      const poll = async () => {
        if (cancelledRef.current) return;
        try {
          const res = await api.backtest.result(id);
          if (cancelledRef.current) return;

          if (res.status === 'queued' || res.status === 'running') {
            setJobStatus(res.status);
            if (Date.now() < deadline) {
              pollTimerRef.current = setTimeout(poll, POLL_INTERVAL_MS);
            } else {
              setError(
                'Backtest timed out after 10 min — the job may still be running in the backend. Check .praxis_logs/backtesting.log or query the job id directly.'
              );
              setStatus('error');
              stopElapsedTimer();
            }
            return;
          }
          if (res.status === 'completed') {
            setJobStatus('completed');
            setResult(res as unknown as BacktestResult);
            setStatus('completed');
            stopElapsedTimer();
            return;
          }
          if (res.status === 'failed') {
            setJobStatus('failed');
            const detail = (res as { error?: string }).error;
            setError(detail ? `Backtest failed: ${detail}` : 'Backtest failed');
            setStatus('error');
            stopElapsedTimer();
            return;
          }
          setError(`Unknown status: ${res.status}`);
          setStatus('error');
          stopElapsedTimer();
        } catch (e: unknown) {
          if (cancelledRef.current) return;
          setError(e instanceof Error ? e.message : 'Failed to fetch result');
          setStatus('error');
          stopElapsedTimer();
        }
      };
      poll();
    },
    [stopElapsedTimer]
  );

  const handleSubmit = async () => {
    setError(null);
    setResult(null);
    setJobStatus(null);
    setElapsedMs(0);

    let parsed;
    try {
      parsed = JSON.parse(rulesJson);
    } catch {
      setError('Invalid JSON in strategy rules');
      return;
    }

    try {
      setStatus('queued');
      setJobStatus('queued');
      setRunConfig({ symbol, start: startDate, end: endDate, slippage });
      startTimeRef.current = Date.now();
      stopElapsedTimer();
      elapsedTimerRef.current = setInterval(() => {
        setElapsedMs(Date.now() - startTimeRef.current);
      }, 1000);

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
      stopElapsedTimer();
    }
  };

  const isRunning = status === 'queued' || status === 'polling';
  const runningLabel =
    jobStatus === 'queued' ? 'Queued' : jobStatus === 'running' ? 'Running' : 'Working';

  return (
    <motion.div variants={pageEnter} initial="initial" animate="animate" className="flex flex-col gap-6 h-full">
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
                {runningLabel} · {formatElapsed(elapsedMs)}
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
              {isRunning && runConfig ? (
                <div className="flex flex-col items-center gap-4 max-w-md w-full">
                  <Loader2 className="w-8 h-8 animate-spin text-primary" />
                  <div className="text-center space-y-1">
                    <p className="text-sm font-medium text-foreground">
                      {runningLabel} · {formatElapsed(elapsedMs)}
                    </p>
                    <p className="text-xs text-muted-foreground font-mono tabular-nums">
                      {runConfig.symbol} · {runConfig.start} → {runConfig.end} · slippage {runConfig.slippage}
                    </p>
                  </div>
                  <p className="text-xs text-muted-foreground/70 text-center max-w-xs">
                    Sequential simulator runs per-candle with Decimal math; multi-month runs at 1m timeframe may take several minutes.
                  </p>
                </div>
              ) : (
                <p className="text-sm text-muted-foreground">
                  Configure and run a backtest to see results
                </p>
              )}
            </div>
          )}
        </div>
      </div>
    </motion.div>
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
