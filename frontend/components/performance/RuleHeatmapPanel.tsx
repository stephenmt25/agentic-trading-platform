"use client";

import { memo, useEffect, useMemo, useState } from "react";
import { InfoTooltip } from "@/components/ui/InfoTooltip";
import { api } from "@/lib/api/client";
import { Loader2 } from "lucide-react";

interface Row {
  fingerprint: string;
  trade_count: number;
  win_count: number;
  loss_count: number;
  breakeven_count: number;
  win_rate: number | null;
  avg_pnl_pct: number | null;
  avg_pnl_usd: number | null;
  first_trade_at: string | null;
  last_trade_at: string | null;
}

interface Props {
  symbol?: string;
  profileId?: string | null;
}

const WINDOW_OPTIONS: Array<{ label: string; hours: number }> = [
  { label: "24h", hours: 24 },
  { label: "7d", hours: 168 },
  { label: "30d", hours: 720 },
];

function fmtPct(value: number | null, signed = false): string {
  if (value == null) return "—";
  const pct = value * 100;
  const formatted = pct.toFixed(2);
  return signed && pct > 0 ? `+${formatted}%` : `${formatted}%`;
}

function fmtUsd(value: number | null): string {
  if (value == null) return "—";
  const sign = value > 0 ? "+" : value < 0 ? "−" : "";
  const abs = Math.abs(value);
  return `${sign}$${abs.toFixed(2)}`;
}

// Render a fingerprint string ("rsi:LT:50 | macd.histogram:GT:0") as
// individual condition pills so the table stays scannable when the
// fingerprint is long.
function FingerprintCell({ fingerprint }: { fingerprint: string }) {
  const parts = fingerprint.split(" | ").map((p) => p.trim());
  return (
    <div className="flex flex-wrap gap-1">
      {parts.map((p, i) => {
        const [indicator, operator, threshold] = p.split(":");
        return (
          <span
            key={i}
            className="inline-flex items-center text-[10px] font-mono bg-zinc-800/70 text-zinc-300 rounded px-1.5 py-0.5"
            title={p}
          >
            <span className="text-zinc-400">{indicator}</span>
            <span className="text-amber-400 mx-0.5">{operator}</span>
            <span className="text-zinc-200">{threshold}</span>
          </span>
        );
      })}
    </div>
  );
}

function RuleHeatmapPanelInner({ symbol, profileId }: Props) {
  const [windowHours, setWindowHours] = useState(720);
  const [minTrades, setMinTrades] = useState(1);
  const [rows, setRows] = useState<Row[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!symbol) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    api.agentPerformance
      .ruleHeatmap(symbol, {
        profileId: profileId ?? undefined,
        windowHours,
        minTrades,
        limit: 50,
      })
      .then((r) => {
        if (!cancelled) setRows(r);
      })
      .catch((e) => {
        if (!cancelled) setError(e instanceof Error ? e.message : "Failed to load rule heatmap");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [symbol, profileId, windowHours, minTrades]);

  const totalTrades = useMemo(() => rows.reduce((acc, r) => acc + r.trade_count, 0), [rows]);

  return (
    <div className="bg-zinc-900/50 rounded-lg border border-zinc-800 p-4">
      <div className="flex items-center justify-between mb-3 gap-3 flex-wrap">
        <h3 className="text-sm font-medium text-zinc-300 flex items-center gap-1.5">
          Rule fingerprint heatmap
          <InfoTooltip text="Closed trades grouped by the exact set of strategy conditions that fired (sorted, so order doesn't matter). Tells you which rule combinations are actually winning vs just generating volume — direct input to the PR4 mutation generator." />
        </h3>
        <div className="flex items-center gap-2 text-xs">
          {WINDOW_OPTIONS.map((w) => (
            <button
              key={w.hours}
              onClick={() => setWindowHours(w.hours)}
              className={`px-2 py-1 rounded transition-colors ${
                windowHours === w.hours
                  ? "bg-primary text-primary-foreground"
                  : "bg-zinc-800 text-zinc-400 hover:text-zinc-200"
              }`}
            >
              {w.label}
            </button>
          ))}
          <label className="flex items-center gap-1 text-zinc-400 ml-2">
            min
            <select
              className="bg-zinc-800 text-zinc-200 rounded px-1 py-0.5"
              value={minTrades}
              onChange={(e) => setMinTrades(Number(e.target.value))}
            >
              <option value={1}>1</option>
              <option value={3}>3</option>
              <option value={5}>5</option>
              <option value={10}>10</option>
            </select>
            trades
          </label>
        </div>
      </div>

      {loading ? (
        <div className="flex items-center justify-center h-32">
          <Loader2 className="w-4 h-4 animate-spin text-zinc-500" />
        </div>
      ) : error ? (
        <div className="text-sm text-red-400 px-1">{error}</div>
      ) : rows.length === 0 ? (
        <div className="text-sm text-zinc-500 text-center py-8">
          No closed trades with rule context in this window
        </div>
      ) : (
        <>
          <div className="text-[11px] text-zinc-500 mb-2">
            {totalTrades} closed trade{totalTrades === 1 ? "" : "s"} across {rows.length} fingerprint{rows.length === 1 ? "" : "s"}
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-zinc-500 border-b border-zinc-800">
                  <th className="text-left py-1.5 pr-2 font-normal">Fingerprint</th>
                  <th className="text-right py-1.5 px-2 font-normal">Trades</th>
                  <th className="text-right py-1.5 px-2 font-normal">Win rate</th>
                  <th className="text-right py-1.5 px-2 font-normal">Avg PnL</th>
                  <th className="text-right py-1.5 px-2 font-normal">Avg $</th>
                  <th className="text-left py-1.5 pl-2 font-normal">W / L / B</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r, i) => {
                  const winRatePct = r.win_rate != null ? r.win_rate * 100 : null;
                  return (
                    <tr key={`${r.fingerprint}-${i}`} className="border-b border-zinc-800/50 align-top">
                      <td className="py-1.5 pr-2 max-w-md">
                        <FingerprintCell fingerprint={r.fingerprint} />
                      </td>
                      <td className="py-1.5 px-2 text-right text-zinc-300">{r.trade_count}</td>
                      <td className="py-1.5 px-2 text-right">
                        {winRatePct == null ? (
                          <span className="text-zinc-500">—</span>
                        ) : (
                          <span
                            className={
                              winRatePct >= 60
                                ? "text-green-400"
                                : winRatePct >= 40
                                ? "text-amber-400"
                                : "text-red-400"
                            }
                          >
                            {winRatePct.toFixed(0)}%
                          </span>
                        )}
                      </td>
                      <td className="py-1.5 px-2 text-right">
                        <span
                          className={
                            r.avg_pnl_pct == null
                              ? "text-zinc-500"
                              : r.avg_pnl_pct > 0
                              ? "text-green-400"
                              : r.avg_pnl_pct < 0
                              ? "text-red-400"
                              : "text-zinc-400"
                          }
                        >
                          {fmtPct(r.avg_pnl_pct, true)}
                        </span>
                      </td>
                      <td className="py-1.5 px-2 text-right text-zinc-400">{fmtUsd(r.avg_pnl_usd)}</td>
                      <td className="py-1.5 pl-2 text-zinc-500">
                        <span className="text-green-500/80">{r.win_count}</span>
                        {" / "}
                        <span className="text-red-500/80">{r.loss_count}</span>
                        {" / "}
                        <span className="text-zinc-500">{r.breakeven_count}</span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}

export const RuleHeatmapPanel = memo(RuleHeatmapPanelInner);
