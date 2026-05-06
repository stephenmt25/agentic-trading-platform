'use client';

import React, { memo, useEffect, useMemo, useState } from 'react';
import { api } from '../../lib/api/client';
import { Loader2, RefreshCw, FolderOpen } from 'lucide-react';

type SortKey = 'created_at' | 'sharpe' | 'avg_return' | 'max_drawdown';

interface HistoryItem {
  job_id: string;
  symbol: string;
  total_trades: number;
  win_rate: string | number;
  avg_return: string | number;
  max_drawdown: string | number;
  sharpe: string | number;
  profit_factor: string | number;
  created_at: string;
  start_date: string | null;
  end_date: string | null;
  timeframe: string | null;
}

interface PastRunsPanelProps {
  // Called when the user clicks "Load" on a past run. Implementation should
  // fetch full result via api.backtest.result(jobId) and merge it into the
  // session-level RunHistoryStrip state.
  onLoad: (jobId: string) => Promise<void>;
  // Optional symbol filter so the embedded /strategies → Verify tab only
  // shows runs for the symbol currently being verified.
  filterSymbol?: string;
  // Bumped by the parent each time a new backtest completes — forces a
  // re-fetch so just-finished runs appear without the user clicking refresh.
  refreshKey?: number;
}

function num(v: string | number): number {
  return typeof v === 'string' ? parseFloat(v) : v;
}

function fmtPct(v: string | number, digits = 2): string {
  const n = num(v);
  if (!Number.isFinite(n)) return '—';
  return `${(n * 100).toFixed(digits)}%`;
}

function fmtNumber(v: string | number, digits = 2): string {
  const n = num(v);
  if (!Number.isFinite(n)) return '—';
  return n.toFixed(digits);
}

function fmtDate(iso: string | null): string {
  if (!iso) return '—';
  const d = new Date(iso);
  return d.toLocaleString(undefined, {
    month: 'short', day: 'numeric',
    hour: '2-digit', minute: '2-digit',
  });
}

const PastRunsPanelImpl: React.FC<PastRunsPanelProps> = ({ onLoad, filterSymbol, refreshKey }) => {
  const [items, setItems] = useState<HistoryItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [loadingId, setLoadingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [sortBy, setSortBy] = useState<SortKey>('created_at');

  const fetchHistory = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.backtest.history({
        symbol: filterSymbol,
        limit: 30,
      });
      setItems(res.items);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to load history');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchHistory();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filterSymbol, refreshKey]);

  const sortedItems = useMemo(() => {
    const copy = [...items];
    copy.sort((a, b) => {
      if (sortBy === 'created_at') {
        return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
      }
      if (sortBy === 'max_drawdown') {
        // Lower drawdown is better — sort ascending so worst is last
        return num(a.max_drawdown) - num(b.max_drawdown);
      }
      return num(b[sortBy]) - num(a[sortBy]);
    });
    return copy;
  }, [items, sortBy]);

  const handleLoad = async (jobId: string) => {
    setLoadingId(jobId);
    try {
      await onLoad(jobId);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to load run');
    } finally {
      setLoadingId(null);
    }
  };

  return (
    <section>
      <div className="flex items-center justify-between mb-2">
        <h2 className="uppercase text-xs font-semibold text-muted-foreground tracking-wider">
          Past Runs{items.length > 0 ? ` (${items.length})` : ''}
        </h2>
        <div className="flex items-center gap-2">
          <select
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value as SortKey)}
            className="text-xs bg-background border border-border rounded-md px-2 py-1 text-foreground focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary cursor-pointer"
          >
            <option value="created_at">Newest first</option>
            <option value="sharpe">Best Sharpe</option>
            <option value="avg_return">Best avg return</option>
            <option value="max_drawdown">Lowest drawdown</option>
          </select>
          <button
            onClick={fetchHistory}
            disabled={loading}
            className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground disabled:opacity-50 transition-colors"
            title="Refresh"
          >
            {loading ? (
              <Loader2 className="w-3 h-3 animate-spin" />
            ) : (
              <RefreshCw className="w-3 h-3" />
            )}
          </button>
        </div>
      </div>

      {error && (
        <div className="text-xs text-red-500 border border-destructive/30 rounded-md p-2 mb-2 font-mono">
          {error}
        </div>
      )}

      {!loading && items.length === 0 && !error && (
        <p className="text-xs text-muted-foreground italic">
          No past runs yet. Completed backtests appear here automatically.
        </p>
      )}

      {sortedItems.length > 0 && (
        <div className="border border-border rounded-md overflow-hidden">
          <div className="max-h-[260px] overflow-y-auto">
            <table className="w-full text-xs font-mono tabular-nums">
              <thead className="sticky top-0 bg-muted/50 backdrop-blur">
                <tr className="text-muted-foreground">
                  <th className="text-left px-3 py-2 font-medium">When</th>
                  <th className="text-left px-3 py-2 font-medium">Symbol</th>
                  <th className="text-right px-3 py-2 font-medium">Trades</th>
                  <th className="text-right px-3 py-2 font-medium">Win</th>
                  <th className="text-right px-3 py-2 font-medium">Sharpe</th>
                  <th className="text-right px-3 py-2 font-medium">Max DD</th>
                  <th className="text-right px-3 py-2 font-medium"></th>
                </tr>
              </thead>
              <tbody>
                {sortedItems.map((it) => (
                  <tr
                    key={it.job_id}
                    className="border-t border-border hover:bg-muted/30 transition-colors"
                  >
                    <td className="px-3 py-2 text-foreground/80">{fmtDate(it.created_at)}</td>
                    <td className="px-3 py-2 text-foreground/80">
                      {it.symbol}
                      {it.timeframe ? ` · ${it.timeframe}` : ''}
                    </td>
                    <td className="px-3 py-2 text-right text-foreground/80">{it.total_trades}</td>
                    <td className="px-3 py-2 text-right text-foreground/80">{fmtPct(it.win_rate, 1)}</td>
                    <td className="px-3 py-2 text-right text-foreground/80">{fmtNumber(it.sharpe)}</td>
                    <td className="px-3 py-2 text-right text-foreground/80">{fmtPct(it.max_drawdown, 1)}</td>
                    <td className="px-3 py-2 text-right">
                      <button
                        onClick={() => handleLoad(it.job_id)}
                        disabled={loadingId === it.job_id}
                        className="inline-flex items-center gap-1 text-xs text-primary hover:underline disabled:opacity-50"
                        title="Load this run into the comparison panel"
                      >
                        {loadingId === it.job_id ? (
                          <Loader2 className="w-3 h-3 animate-spin" />
                        ) : (
                          <FolderOpen className="w-3 h-3" />
                        )}
                        Load
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </section>
  );
};

export const PastRunsPanel = memo(PastRunsPanelImpl);
