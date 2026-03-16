'use client';

import React, { useState, useCallback, useRef, useEffect } from 'react';
import { api } from '../../lib/api/client';
import { BacktestResult, SimulatedTrade } from '../../lib/types';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { EquityCurveChart } from '@/components/backtest/EquityCurveChart';
import { TradesTable } from '@/components/backtest/TradesTable';
import { Loader2, Play, BarChart3, TrendingUp, TrendingDown, Target, Percent, Activity } from 'lucide-react';

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
      <h1 className="text-3xl font-black tracking-tight text-white border-b border-border pb-4">
        BACKTEST ENGINE
      </h1>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        {/* Left: Configuration */}
        <Card className="border-border bg-card shadow-2xl xl:col-span-1">
          <CardHeader>
            <CardTitle className="uppercase text-xs font-bold text-muted-foreground tracking-wider">
              Configuration
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <label className="text-[10px] uppercase text-muted-foreground font-bold tracking-wider block mb-1.5">
                Symbol
              </label>
              <Input
                value={symbol}
                onChange={(e) => setSymbol(e.target.value)}
                className="font-mono bg-black/20 border-border"
                placeholder="BTC/USDT"
              />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-[10px] uppercase text-muted-foreground font-bold tracking-wider block mb-1.5">
                  Start Date
                </label>
                <Input
                  type="date"
                  value={startDate}
                  onChange={(e) => setStartDate(e.target.value)}
                  className="font-mono bg-black/20 border-border text-xs"
                />
              </div>
              <div>
                <label className="text-[10px] uppercase text-muted-foreground font-bold tracking-wider block mb-1.5">
                  End Date
                </label>
                <Input
                  type="date"
                  value={endDate}
                  onChange={(e) => setEndDate(e.target.value)}
                  className="font-mono bg-black/20 border-border text-xs"
                />
              </div>
            </div>

            <div>
              <label className="text-[10px] uppercase text-muted-foreground font-bold tracking-wider block mb-1.5">
                Slippage %
              </label>
              <Input
                value={slippage}
                onChange={(e) => setSlippage(e.target.value)}
                className="font-mono bg-black/20 border-border"
                placeholder="0.001"
                type="number"
                step="0.0001"
              />
            </div>

            <div>
              <label className="text-[10px] uppercase text-muted-foreground font-bold tracking-wider block mb-1.5">
                Strategy Rules (JSON)
              </label>
              <textarea
                value={rulesJson}
                onChange={(e) => setRulesJson(e.target.value)}
                className="w-full h-40 font-mono text-xs bg-black/30 border border-border rounded-lg p-3 text-slate-300 resize-none focus:outline-none focus:ring-1 focus:ring-primary"
                spellCheck={false}
              />
            </div>

            <Button
              onClick={handleSubmit}
              disabled={isRunning}
              className="w-full font-bold tracking-wider"
            >
              {isRunning ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  {status === 'queued' ? 'QUEUED...' : 'RUNNING...'}
                </>
              ) : (
                <>
                  <Play className="w-4 h-4 mr-2" />
                  RUN BACKTEST
                </>
              )}
            </Button>

            {error && (
              <div className="text-xs text-rose-400 bg-rose-950/30 border border-rose-500/30 rounded-lg p-3 font-mono">
                {error}
              </div>
            )}

            {jobId && (
              <div className="text-[10px] text-muted-foreground font-mono">
                Job ID: {jobId}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Right: Results */}
        <div className="xl:col-span-2 flex flex-col gap-6">
          {result ? (
            <>
              {/* Metrics Grid */}
              <div className="grid grid-cols-2 lg:grid-cols-3 gap-4">
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
                <Card className="border-border bg-card shadow-2xl">
                  <CardHeader>
                    <CardTitle className="uppercase text-xs font-bold text-muted-foreground tracking-wider">
                      Equity Curve
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <EquityCurveChart data={result.equity_curve} />
                  </CardContent>
                </Card>
              )}

              {/* Trades Table */}
              {result.trades && result.trades.length > 0 && (
                <Card className="border-border bg-card shadow-2xl">
                  <CardHeader>
                    <CardTitle className="uppercase text-xs font-bold text-muted-foreground tracking-wider">
                      Simulated Trades ({result.trades.length})
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <TradesTable trades={result.trades} />
                  </CardContent>
                </Card>
              )}
            </>
          ) : (
            <Card className="border-border bg-card shadow-2xl flex-1">
              <CardContent className="h-full flex flex-col items-center justify-center gap-3 py-20">
                <BarChart3 className="w-12 h-12 text-muted-foreground/30" />
                <p className="text-sm text-muted-foreground font-mono">
                  {isRunning ? 'Running simulation...' : 'Configure and run a backtest to see results'}
                </p>
              </CardContent>
            </Card>
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
  color = 'slate',
}: {
  label: string;
  value: string;
  icon: React.ReactNode;
  color?: string;
}) {
  const colorMap: Record<string, string> = {
    emerald: 'text-emerald-400',
    rose: 'text-rose-400',
    amber: 'text-amber-400',
    slate: 'text-slate-300',
  };

  return (
    <Card className="border-border bg-card shadow-lg">
      <CardContent className="p-4">
        <div className="flex items-center gap-2 mb-2">
          <span className="text-muted-foreground">{icon}</span>
          <span className="text-[10px] uppercase text-muted-foreground font-bold tracking-wider">
            {label}
          </span>
        </div>
        <span className={`text-2xl font-mono font-bold ${colorMap[color] || colorMap.slate}`}>
          {value}
        </span>
      </CardContent>
    </Card>
  );
}
