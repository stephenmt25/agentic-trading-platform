"use client";

import { memo, useEffect, useMemo, useState } from "react";
import { InfoTooltip } from "@/components/ui/InfoTooltip";
import { api } from "@/lib/api/client";
import { Loader2 } from "lucide-react";

type Dimension =
  | "symbol"
  | "side"
  | "regime"
  | "outcome"
  | "close_reason"
  | "hold_duration"
  | "hour"
  | "day_of_week";

interface Row {
  bucket: string;
  count: number;
  win_count: number;
  loss_count: number;
  breakeven_count: number;
  win_rate: number | null;
  avg_pnl_pct: number | null;
  avg_pnl_usd: number | null;
}

interface Props {
  symbol?: string;
  profileId?: string | null;
}

const DIMENSIONS: Array<{ id: Dimension; label: string; hint: string }> = [
  {
    id: "symbol",
    label: "Symbol",
    hint: "Per-symbol outcomes — the strategy may work on one pair but lose on another.",
  },
  {
    id: "side",
    label: "Direction (BUY / SELL)",
    hint: "Long versus short outcomes — the headline split for any both-legs profile.",
  },
  {
    id: "regime",
    label: "Entry regime",
    hint: "How trades opened in each HMM regime have actually paid off. Buckets labelled 'unknown' have no regime persisted at entry.",
  },
  {
    id: "outcome",
    label: "Outcome",
    hint: "Sanity slice — counts by the recorded outcome label (win / loss / breakeven).",
  },
  {
    id: "close_reason",
    label: "Close reason",
    hint: "Same dimension as the Close reasons tab; included here for completeness when you're slicing by attribute.",
  },
  {
    id: "hold_duration",
    label: "Hold duration",
    hint: "Quick-flips vs swings. < 1h, 1–6h, 6–24h, ≥ 24h.",
  },
  {
    id: "hour",
    label: "Hour of day (UTC)",
    hint: "Time-of-day clustering. Bucketed night / morning / afternoon / evening (UTC).",
  },
  {
    id: "day_of_week",
    label: "Day of week (UTC)",
    hint: "Weekday clustering of opens. UTC.",
  },
];

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

function TradeAttributesPanelInner({ symbol, profileId }: Props) {
  const [dimension, setDimension] = useState<Dimension>("side");
  const [windowHours, setWindowHours] = useState(168);
  const [rows, setRows] = useState<Row[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!symbol) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    api.agentPerformance
      .tradeAttribute(symbol, dimension, {
        profileId: profileId ?? undefined,
        windowHours,
        limit: 50,
      })
      .then((r) => {
        if (!cancelled) setRows(r);
      })
      .catch((e) => {
        if (!cancelled) setError(e instanceof Error ? e.message : "Failed to load");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [symbol, profileId, dimension, windowHours]);

  const totalCount = useMemo(() => rows.reduce((acc, r) => acc + r.count, 0), [rows]);
  const activeDim = DIMENSIONS.find((d) => d.id === dimension)!;

  return (
    <div className="bg-zinc-900/50 rounded-lg border border-zinc-800 p-4">
      <div className="flex items-center justify-between mb-3 gap-3 flex-wrap">
        <h3 className="text-sm font-medium text-zinc-300 flex items-center gap-1.5">
          Trade attributes
          <InfoTooltip text="Slice closed trades by a single attribute (direction, regime, hold duration, hour-of-day, weekday). Same shape as the other forensics panels — count, win rate, avg PnL — bucketed by the attribute you pick." />
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
        </div>
      </div>

      <div className="mb-3 flex items-center gap-2 text-xs">
        <label className="text-zinc-400">Slice by</label>
        <select
          className="bg-zinc-800 text-zinc-200 rounded px-2 py-1"
          value={dimension}
          onChange={(e) => setDimension(e.target.value as Dimension)}
        >
          {DIMENSIONS.map((d) => (
            <option key={d.id} value={d.id}>
              {d.label}
            </option>
          ))}
        </select>
      </div>

      <p className="text-[11px] text-zinc-500 mb-2">{activeDim.hint}</p>

      {loading ? (
        <div className="flex items-center justify-center h-32">
          <Loader2 className="w-4 h-4 animate-spin text-zinc-500" />
        </div>
      ) : error ? (
        <div className="text-sm text-red-400 px-1">{error}</div>
      ) : rows.length === 0 ? (
        <div className="text-sm text-zinc-500 text-center py-8">
          No closed trades in this window
        </div>
      ) : (
        <>
          <div className="text-[11px] text-zinc-500 mb-2">
            {totalCount} closed trade{totalCount === 1 ? "" : "s"} across {rows.length} bucket{rows.length === 1 ? "" : "s"}
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-zinc-500 border-b border-zinc-800">
                  <th className="text-left py-1.5 pr-2 font-normal">Bucket</th>
                  <th className="text-right py-1.5 px-2 font-normal">Count</th>
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
                    <tr key={`${r.bucket}-${i}`} className="border-b border-zinc-800/50">
                      <td className="py-1.5 pr-2 text-zinc-300">{r.bucket}</td>
                      <td className="py-1.5 px-2 text-right text-zinc-300">{r.count}</td>
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

export const TradeAttributesPanel = memo(TradeAttributesPanelInner);
