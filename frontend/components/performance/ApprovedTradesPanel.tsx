"use client";

import { memo, useEffect, useMemo, useState } from "react";
import { InfoTooltip } from "@/components/ui/InfoTooltip";
import { api } from "@/lib/api/client";
import { Loader2 } from "lucide-react";

type Dimension = "symbol" | "direction" | "regime" | "hour" | "day_of_week";

interface Row {
  bucket: string;
  count: number;
  percent: number | null;
}

interface Props {
  symbol?: string;
  profileId?: string | null;
}

const DIMENSIONS: Array<{ id: Dimension; label: string; hint: string }> = [
  {
    id: "symbol",
    label: "Symbol",
    hint: "Distribution of approved decisions across trading symbols.",
  },
  {
    id: "direction",
    label: "Direction (BUY / SELL)",
    hint: "Long-bias vs short-bias of approved decisions.",
  },
  {
    id: "regime",
    label: "Regime",
    hint: "HMM regime at decision time. 'unknown' when regime context was not captured.",
  },
  {
    id: "hour",
    label: "Hour of day (UTC)",
    hint: "When approvals cluster in the trading day.",
  },
  {
    id: "day_of_week",
    label: "Day of week (UTC)",
    hint: "Weekday distribution of approvals.",
  },
];

const WINDOW_OPTIONS: Array<{ label: string; hours: number }> = [
  { label: "24h", hours: 24 },
  { label: "7d", hours: 168 },
  { label: "30d", hours: 720 },
];

function fmtPct(value: number | null): string {
  if (value == null) return "—";
  return `${(value * 100).toFixed(1)}%`;
}

function ApprovedTradesPanelInner({ symbol, profileId }: Props) {
  const [dimension, setDimension] = useState<Dimension>("direction");
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
      .approvedAttribute(symbol, dimension, {
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
          Approved decisions
          <InfoTooltip text="Distribution of decisions that passed every gate, regardless of whether the resulting position has closed yet. Use the Closed Trades tab for realized win-rate / PnL." />
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
          No approved decisions in this window
        </div>
      ) : (
        <>
          <div className="text-[11px] text-zinc-500 mb-2">
            {totalCount} approved decision{totalCount === 1 ? "" : "s"} across {rows.length} bucket{rows.length === 1 ? "" : "s"}
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-zinc-500 border-b border-zinc-800">
                  <th className="text-left py-1.5 pr-2 font-normal">Bucket</th>
                  <th className="text-right py-1.5 px-2 font-normal">Count</th>
                  <th className="text-right py-1.5 px-2 font-normal">% of total</th>
                  <th className="text-left py-1.5 pl-3 font-normal">Share</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r, i) => {
                  const pct = r.percent != null ? r.percent * 100 : 0;
                  return (
                    <tr key={`${r.bucket}-${i}`} className="border-b border-zinc-800/50">
                      <td className="py-1.5 pr-2 text-zinc-300">{r.bucket}</td>
                      <td className="py-1.5 px-2 text-right text-zinc-300">{r.count}</td>
                      <td className="py-1.5 px-2 text-right text-zinc-400">{fmtPct(r.percent)}</td>
                      <td className="py-1.5 pl-3 w-32">
                        <div className="w-full bg-zinc-800 rounded-full h-1.5">
                          <div
                            className="bg-blue-400/70 h-1.5 rounded-full"
                            style={{ width: `${Math.min(100, pct)}%` }}
                          />
                        </div>
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

export const ApprovedTradesPanel = memo(ApprovedTradesPanelInner);
