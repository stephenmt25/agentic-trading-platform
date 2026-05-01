'use client';

import React, { useState, useCallback, useMemo, useRef, useEffect } from 'react';
import { usePathname } from 'next/navigation';
import { api } from '../../lib/api/client';
import { BacktestResult, RunConfig, StoredRun } from '../../lib/types';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { EquityCurveChart, EquitySeries } from '@/components/backtest/EquityCurveChart';
import { TradesTable } from '@/components/backtest/TradesTable';
import { RunHistoryStrip } from '@/components/backtest/RunHistoryStrip';
import { ComparisonTable } from '@/components/backtest/ComparisonTable';
import { Loader2, Play, AlertTriangle } from 'lucide-react';
import { motion } from "framer-motion";
import { pageEnter } from "@/lib/motion";

const DEFAULT_RULES = JSON.stringify(
  {
    direction: 'long',
    match_mode: 'all',
    confidence: 0.85,
    signals: [{ indicator: 'rsi', comparison: 'below', threshold: 30 }],
  },
  null,
  2
);

const TIMEFRAMES = ['1m', '5m', '15m', '1h', '1d'] as const;
type Timeframe = (typeof TIMEFRAMES)[number];

const PALETTE = [
  '#10b981', '#6366f1', '#f59e0b', '#ef4444',
  '#8b5cf6', '#ec4899', '#14b8a6', '#f97316',
];

const COMPARISON_SYMBOLS: Record<string, string> = {
  below: '<', above: '>', at_or_below: '≤', at_or_above: '≥', equals: '=',
};

function toDateInput(d: Date): string {
  return d.toISOString().slice(0, 10);
}

function defaultDateRange(): { start: string; end: string } {
  const end = new Date();
  const start = new Date();
  start.setDate(end.getDate() - 5);
  return { start: toDateInput(start), end: toDateInput(end) };
}

function generateLabel(cfg: RunConfig): string {
  const base = cfg.symbol.split('/')[0] || cfg.symbol;
  const parts: string[] = [base, cfg.timeframe];
  try {
    const rules = JSON.parse(cfg.rulesJson);
    const first = rules?.signals?.[0];
    if (first && typeof first === 'object') {
      const op = COMPARISON_SYMBOLS[first.comparison] ?? first.comparison;
      parts.push(`${first.indicator}${op}${first.threshold}`);
    }
    if (rules?.direction) parts.push(rules.direction);
  } catch {
    // malformed rules — skip condition fragment
  }
  return parts.join('·');
}

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
  // Embedded mode (inside /strategies → Verify tab) hides the rule editor and
  // forces backtests to run against an existing profile's stored canonical rules.
  const pathname = usePathname();
  const isEmbedded = pathname?.startsWith('/strategies') ?? false;

  const [symbol, setSymbol] = useState('BTC/USDT');
  const [startDate, setStartDate] = useState(() => defaultDateRange().start);
  const [endDate, setEndDate] = useState(() => defaultDateRange().end);
  const [timeframe, setTimeframe] = useState<Timeframe>('1m');
  const [slippage, setSlippage] = useState('0.001');
  const [rulesJson, setRulesJson] = useState(DEFAULT_RULES);
  const [selectedProfileId, setSelectedProfileId] = useState<string | null>(null);
  const [profiles, setProfiles] = useState<Array<{ profile_id: string; name: string; rules_json: Record<string, unknown> }>>([]);
  const [jobId, setJobId] = useState<string | null>(null);
  const [status, setStatus] = useState<'idle' | 'queued' | 'polling' | 'completed' | 'error'>('idle');
  const [jobStatus, setJobStatus] = useState<BackendJobStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [runConfig, setRunConfig] = useState<{ symbol: string; start: string; end: string; timeframe: string; slippage: string } | null>(null);
  const [elapsedMs, setElapsedMs] = useState(0);
  const [runs, setRuns] = useState<StoredRun[]>([]);
  const [activeRunId, setActiveRunId] = useState<string | null>(null);

  const pollTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const elapsedTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const startTimeRef = useRef<number>(0);
  const cancelledRef = useRef(false);
  const pendingConfigRef = useRef<RunConfig | null>(null);
  const colorCursorRef = useRef(0);
  const runsRef = useRef<StoredRun[]>([]);
  useEffect(() => {
    runsRef.current = runs;
  }, [runs]);

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

  // Load strategies (profiles) once so the picker dropdown is populated
  useEffect(() => {
    let cancelled = false;
    api.profiles.list()
      .then((res) => {
        if (cancelled) return;
        const active = res
          .filter((p) => !p.deleted_at)
          .map((p) => ({
            profile_id: p.profile_id,
            name: p.name,
            rules_json: p.rules_json as Record<string, unknown>,
          }));
        setProfiles(active);
      })
      .catch(() => {
        // Silent — profile loading is best-effort; user can still paste JSON
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const handleLoadStrategy = useCallback((profileId: string) => {
    if (!profileId) return;
    const profile = profiles.find((p) => p.profile_id === profileId);
    if (!profile) return;
    setRulesJson(JSON.stringify(profile.rules_json, null, 2));
    setSelectedProfileId(profileId);
  }, [profiles]);

  // Embedded mode: auto-select the first profile so the form is immediately runnable.
  useEffect(() => {
    if (!isEmbedded) return;
    if (selectedProfileId) return;
    if (profiles.length === 0) return;
    handleLoadStrategy(profiles[0].profile_id);
  }, [isEmbedded, selectedProfileId, profiles, handleLoadStrategy]);

  // Sort: pinned first, then most-recently completed first
  const sortedRuns = useMemo(() => {
    return [...runs].sort((a, b) => {
      if (a.pinned !== b.pinned) return a.pinned ? -1 : 1;
      return b.completedAt - a.completedAt;
    });
  }, [runs]);

  const activeRun = useMemo(
    () => runs.find((r) => r.id === activeRunId) ?? null,
    [runs, activeRunId]
  );
  const result: BacktestResult | null = activeRun?.result ?? null;

  const equitySeries: EquitySeries[] = useMemo(
    () =>
      sortedRuns
        .filter((r) => r.visible && r.result.equity_curve?.length > 0)
        .map((r) => ({
          id: r.id,
          label: r.label,
          color: r.color,
          data: r.result.equity_curve,
        })),
    [sortedRuns]
  );

  const visibleRuns = useMemo(() => sortedRuns.filter((r) => r.visible), [sortedRuns]);

  const comparisonRuns = useMemo(
    () => (visibleRuns.length > 0 ? visibleRuns : activeRun ? [activeRun] : []),
    [visibleRuns, activeRun]
  );

  const addCompletedRun = useCallback((res: BacktestResult, config: RunConfig) => {
    const newRun: StoredRun = {
      id: res.job_id,
      label: generateLabel(config),
      pinned: false,
      visible: true,
      color: PALETTE[colorCursorRef.current % PALETTE.length],
      completedAt: Date.now(),
      config,
      result: res,
    };
    colorCursorRef.current += 1;
    setRuns((prev) => {
      if (prev.some((r) => r.id === newRun.id)) return prev;
      return [...prev, newRun];
    });
    setActiveRunId(newRun.id);
  }, []);

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
            const cfg = pendingConfigRef.current;
            if (cfg) {
              addCompletedRun(res as unknown as BacktestResult, cfg);
              pendingConfigRef.current = null;
            }
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
    [stopElapsedTimer, addCompletedRun]
  );

  const handleSubmit = async () => {
    setError(null);
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
      setRunConfig({ symbol, start: startDate, end: endDate, timeframe, slippage });
      pendingConfigRef.current = {
        symbol,
        start: startDate,
        end: endDate,
        timeframe,
        slippage,
        rulesJson,
      };
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
        timeframe,
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

  const handleSelect = useCallback((id: string) => {
    setActiveRunId(id);
  }, []);

  const handleToggleVisible = useCallback((id: string) => {
    setRuns((prev) => prev.map((r) => (r.id === id ? { ...r, visible: !r.visible } : r)));
  }, []);

  const handleTogglePinned = useCallback((id: string) => {
    setRuns((prev) => prev.map((r) => (r.id === id ? { ...r, pinned: !r.pinned } : r)));
  }, []);

  const handleRename = useCallback((id: string, label: string) => {
    setRuns((prev) => prev.map((r) => (r.id === id ? { ...r, label } : r)));
  }, []);

  const handleClone = useCallback((id: string) => {
    const run = runsRef.current.find((r) => r.id === id);
    if (!run) return;
    setSymbol(run.config.symbol);
    setStartDate(run.config.start);
    setEndDate(run.config.end);
    setTimeframe(run.config.timeframe as Timeframe);
    setSlippage(run.config.slippage);
    setRulesJson(run.config.rulesJson);
  }, []);

  const handleDelete = useCallback((id: string) => {
    setRuns((prev) => prev.filter((r) => r.id !== id));
    setActiveRunId((curr) => {
      if (curr !== id) return curr;
      const remaining = runsRef.current.filter((r) => r.id !== id);
      return remaining[0]?.id ?? null;
    });
  }, []);

  const handleClearUnpinned = useCallback(() => {
    setRuns((prev) => prev.filter((r) => r.pinned));
    setActiveRunId((curr) => {
      if (!curr) return null;
      const stillThere = runsRef.current.find((r) => r.id === curr && r.pinned);
      return stillThere ? curr : null;
    });
  }, []);

  const isRunning = status === 'queued' || status === 'polling';
  const runningLabel =
    jobStatus === 'queued' ? 'Queued' : jobStatus === 'running' ? 'Running' : 'Working';

  return (
    <motion.div variants={pageEnter} initial="initial" animate="animate" className="flex flex-col gap-6 h-full">
      {!isEmbedded && (
        <h1 className="text-xl font-semibold tracking-tight text-foreground border-b border-border pb-4">
          Backtest Engine
        </h1>
      )}

      <RunHistoryStrip
        runs={sortedRuns}
        activeRunId={activeRunId}
        onSelect={handleSelect}
        onToggleVisible={handleToggleVisible}
        onTogglePinned={handleTogglePinned}
        onClone={handleClone}
        onDelete={handleDelete}
        onRename={handleRename}
        onClearUnpinned={handleClearUnpinned}
      />

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

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs uppercase text-muted-foreground font-medium tracking-wider block mb-1.5">
                Timeframe
              </label>
              <select
                value={timeframe}
                onChange={(e) => setTimeframe(e.target.value as Timeframe)}
                className="w-full font-mono tabular-nums bg-background border border-border rounded-md min-h-[44px] px-3 text-sm text-foreground focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
              >
                {TIMEFRAMES.map((tf) => (
                  <option key={tf} value={tf}>
                    {tf}
                  </option>
                ))}
              </select>
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
          </div>

          {isEmbedded ? (
            <div>
              <label className="text-xs uppercase text-muted-foreground font-medium tracking-wider block mb-1.5">
                Profile
              </label>
              <select
                value={selectedProfileId ?? ''}
                onChange={(e) => handleLoadStrategy(e.target.value)}
                className="w-full font-mono tabular-nums bg-background border border-border rounded-md min-h-[44px] px-3 text-sm text-foreground focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
              >
                {profiles.length === 0 && <option value="">No profiles yet — create one in Builder</option>}
                {profiles.map((p) => (
                  <option key={p.profile_id} value={p.profile_id}>
                    {p.name}
                  </option>
                ))}
              </select>
              <p className="text-[11px] text-muted-foreground mt-1.5">
                The backtest runs against this profile's saved rules. Edit rules in the Builder tab.
              </p>
            </div>
          ) : (
            <div>
              <div className="flex items-center justify-between mb-1.5 gap-2">
                <label className="text-xs uppercase text-muted-foreground font-medium tracking-wider">
                  Strategy Rules (JSON)
                </label>
                {profiles.length > 0 && (
                  <select
                    value=""
                    onChange={(e) => {
                      handleLoadStrategy(e.target.value);
                      e.target.value = '';
                    }}
                    className="text-xs bg-background border border-border rounded-md px-2 py-1 text-foreground focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary cursor-pointer"
                    title="Load strategy rules from a saved profile"
                  >
                    <option value="">Load from Strategy…</option>
                    {profiles.map((p) => (
                      <option key={p.profile_id} value={p.profile_id}>
                        {p.name}
                      </option>
                    ))}
                  </select>
                )}
              </div>
              <textarea
                value={rulesJson}
                onChange={(e) => setRulesJson(e.target.value)}
                className="w-full h-80 font-mono tabular-nums text-sm bg-background border border-border rounded-md p-3 text-foreground/80 resize-y focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
                spellCheck={false}
              />
            </div>
          )}

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
              {/* Active-run heading */}
              {activeRun && (
                <div className="flex flex-wrap items-center gap-3 pb-2 border-b border-border">
                  <span
                    className="w-3 h-3 rounded-full shrink-0"
                    style={{ backgroundColor: activeRun.color }}
                  />
                  <h2 className="text-base font-semibold text-foreground truncate">
                    {activeRun.label}
                  </h2>
                  <span className="text-xs text-muted-foreground font-mono tabular-nums">
                    {activeRun.config.symbol} · {activeRun.config.timeframe} · {activeRun.config.start} → {activeRun.config.end}
                  </span>
                </div>
              )}

              {/* Equity Curve — overlay for all visible runs; active run highlighted */}
              {equitySeries.length > 0 && (
                <section className="border-t border-border pt-4">
                  <h2 className="uppercase text-xs font-semibold text-muted-foreground tracking-wider mb-4">
                    Equity Curve{equitySeries.length > 1 ? ` · ${equitySeries.length} runs` : ''}
                  </h2>
                  <EquityCurveChart series={equitySeries} activeId={activeRunId} />
                </section>
              )}

              {/* Metrics — single source of truth.
                  1 run: shows that run; 2+ runs: comparison view, best per column highlighted. */}
              {comparisonRuns.length > 0 && (
                <section className="border-t border-border pt-4">
                  <h2 className="uppercase text-xs font-semibold text-muted-foreground tracking-wider mb-4">
                    {comparisonRuns.length === 1 ? 'Metrics' : `Comparison · ${comparisonRuns.length} runs`}
                  </h2>
                  <ComparisonTable runs={comparisonRuns} />
                </section>
              )}

              {/* Trades Table — active run */}
              {result.trades && result.trades.length > 0 && (
                <section className="border-t border-border pt-4">
                  <h2 className="uppercase text-xs font-semibold text-muted-foreground tracking-wider mb-4">
                    Simulated Trades ({result.trades.length}) · {activeRun?.label ?? ''}
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
                      {runConfig.symbol} · {runConfig.timeframe} · {runConfig.start} → {runConfig.end} · slippage {runConfig.slippage}
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
