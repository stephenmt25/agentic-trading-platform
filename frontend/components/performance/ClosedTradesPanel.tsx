"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api/client";
import { InfoTooltip } from "@/components/ui/InfoTooltip";

type ClosedTrade = Awaited<ReturnType<typeof api.audit.closedTrades>>[number];

interface Props {
  symbol: string;
  limit?: number;
}

const PAGE_SIZE = 20;

function fmtDateTime(iso: string): { date: string; time: string } {
  const d = new Date(iso);
  return {
    date: d.toLocaleDateString([], { year: "numeric", month: "short", day: "numeric" }),
    time: d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" }),
  };
}

function fmtDuration(seconds: number): string {
  if (seconds < 60) return `${seconds}s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m`;
  if (seconds < 86400) return `${(seconds / 3600).toFixed(1)}h`;
  return `${(seconds / 86400).toFixed(1)}d`;
}

export function ClosedTradesPanel({ symbol, limit = 100 }: Props) {
  const [trades, setTrades] = useState<ClosedTrade[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    api.audit
      .closedTrades({ symbol, limit })
      .then((rows) => {
        if (!cancelled) {
          setTrades(rows);
          setPage(0);
        }
      })
      .catch((e) => {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : "Failed to load closed trades");
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [symbol, limit]);

  if (loading) {
    return (
      <div className="bg-zinc-900/50 rounded-lg border border-zinc-800 p-6 text-center text-sm text-zinc-500">
        Loading closed trades…
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-zinc-900/50 rounded-lg border border-zinc-800 p-6 text-center text-sm text-red-400">
        {error}
      </div>
    );
  }

  if (!trades.length) {
    return (
      <div className="bg-zinc-900/50 rounded-lg border border-zinc-800 p-6 text-center text-sm text-zinc-500">
        No closed trades for {symbol} yet. Each closed position will appear here with its
        realised P&amp;L and outcome.
      </div>
    );
  }

  const totalPages = Math.ceil(trades.length / PAGE_SIZE);
  const paginated = trades.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);

  // Summary header — wins / losses / breakeven count and aggregate P&L.
  const wins = trades.filter((t) => t.outcome === "win").length;
  const losses = trades.filter((t) => t.outcome === "loss").length;
  const breakeven = trades.filter((t) => t.outcome === "breakeven").length;
  const totalPnl = trades.reduce((acc, t) => acc + t.realized_pnl, 0);

  return (
    <div className="bg-zinc-900/50 rounded-lg border border-zinc-800 overflow-hidden">
      <div className="px-4 py-3 border-b border-zinc-800 flex items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-medium text-zinc-300 flex items-center gap-1.5">
            Closed Trades
            <InfoTooltip text="Every position that has been closed — ordered most-recent first. P&L is realised after fees. Outcome is computed from post-tax pct return." />
          </h3>
          <p className="text-xs text-zinc-500 mt-0.5">
            {trades.length} trade{trades.length === 1 ? "" : "s"} for {symbol}
          </p>
        </div>
        <div className="flex items-center gap-3 text-xs font-mono shrink-0">
          <span className="text-emerald-400">{wins}W</span>
          <span className="text-red-400">{losses}L</span>
          {breakeven > 0 && <span className="text-zinc-500">{breakeven}B</span>}
          <span className={totalPnl >= 0 ? "text-emerald-400" : "text-red-400"}>
            {totalPnl >= 0 ? "+" : ""}${totalPnl.toFixed(2)}
          </span>
        </div>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-zinc-800 text-zinc-500 text-xs">
              <th className="text-left px-4 py-2 font-medium">Date</th>
              <th className="text-left px-4 py-2 font-medium">Closed</th>
              <th className="text-left px-4 py-2 font-medium">Side</th>
              <th className="text-right px-4 py-2 font-medium">Entry</th>
              <th className="text-right px-4 py-2 font-medium">Exit</th>
              <th className="text-right px-4 py-2 font-medium">Hold</th>
              <th className="text-right px-4 py-2 font-medium">P&amp;L</th>
              <th className="text-right px-4 py-2 font-medium">P&amp;L %</th>
              <th className="text-left px-4 py-2 font-medium">Reason</th>
              <th className="text-left px-4 py-2 font-medium">Outcome</th>
            </tr>
          </thead>
          <tbody>
            {paginated.map((trade) => {
              const opened = fmtDateTime(trade.opened_at);
              const closed = fmtDateTime(trade.closed_at);
              const outcomeColor =
                trade.outcome === "win"
                  ? "text-emerald-400"
                  : trade.outcome === "loss"
                  ? "text-red-400"
                  : "text-zinc-500";
              const pnlColor =
                trade.realized_pnl > 0
                  ? "text-emerald-400"
                  : trade.realized_pnl < 0
                  ? "text-red-400"
                  : "text-zinc-500";
              return (
                <tr
                  key={trade.position_id}
                  className="border-b border-zinc-800/50 hover:bg-zinc-800/30"
                >
                  <td className="px-4 py-2 text-zinc-400 text-xs font-mono whitespace-nowrap">
                    {opened.date}
                    <span className="text-zinc-600 ml-1">{opened.time}</span>
                  </td>
                  <td className="px-4 py-2 text-zinc-400 text-xs font-mono whitespace-nowrap">
                    {closed.date === opened.date ? closed.time : `${closed.date} ${closed.time}`}
                  </td>
                  <td className="px-4 py-2 font-mono text-xs">
                    <span
                      className={
                        trade.side === "BUY" ? "text-emerald-400" : "text-red-400"
                      }
                    >
                      {trade.side}
                    </span>
                  </td>
                  <td className="text-right px-4 py-2 font-mono text-zinc-300 tabular-nums">
                    ${trade.entry_price.toFixed(2)}
                  </td>
                  <td className="text-right px-4 py-2 font-mono text-zinc-300 tabular-nums">
                    ${trade.exit_price.toFixed(2)}
                  </td>
                  <td className="text-right px-4 py-2 font-mono text-zinc-400 tabular-nums">
                    {fmtDuration(trade.holding_duration_s)}
                  </td>
                  <td className={`text-right px-4 py-2 font-mono tabular-nums ${pnlColor}`}>
                    {trade.realized_pnl >= 0 ? "+" : ""}${trade.realized_pnl.toFixed(2)}
                  </td>
                  <td className={`text-right px-4 py-2 font-mono tabular-nums ${pnlColor}`}>
                    {trade.realized_pnl_pct >= 0 ? "+" : ""}
                    {(trade.realized_pnl_pct * 100).toFixed(2)}%
                  </td>
                  <td className="px-4 py-2 text-zinc-400 text-xs font-mono">
                    {trade.close_reason}
                  </td>
                  <td className={`px-4 py-2 font-mono text-xs uppercase ${outcomeColor}`}>
                    {trade.outcome}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {totalPages > 1 && (
        <div className="flex items-center justify-between px-4 py-2 text-xs text-zinc-500 border-t border-zinc-800">
          <span>
            Showing {page * PAGE_SIZE + 1}–
            {Math.min((page + 1) * PAGE_SIZE, trades.length)} of {trades.length}
          </span>
          <div className="flex gap-2">
            <button
              onClick={() => setPage(Math.max(0, page - 1))}
              disabled={page === 0}
              className="px-3 py-1 border border-zinc-700 rounded disabled:opacity-30 hover:bg-zinc-800 transition-colors"
            >
              Prev
            </button>
            <button
              onClick={() => setPage(Math.min(totalPages - 1, page + 1))}
              disabled={page >= totalPages - 1}
              className="px-3 py-1 border border-zinc-700 rounded disabled:opacity-30 hover:bg-zinc-800 transition-colors"
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
