"use client";

import { memo, useEffect, useMemo, useState } from "react";
import { InfoTooltip } from "@/components/ui/InfoTooltip";
import { api } from "@/lib/api/client";
import { Loader2 } from "lucide-react";

interface Row {
  pattern: string;
  ta_bucket: string;
  sent_bucket: string;
  debate_bucket: string;
  count: number;
  win_count: number;
  loss_count: number;
  breakeven_count: number;
  win_rate: number | null;
  avg_pnl_pct: number | null;
  avg_pnl_usd: number | null;
  avg_confidence_lift: number | null;
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

const STANCE_COLOR: Record<string, string> = {
  BULL: "text-green-400",
  BEAR: "text-red-400",
  NEUTRAL: "text-zinc-500",
};

function stanceFromBucket(bucket: string): "BULL" | "BEAR" | "NEUTRAL" {
  if (bucket.endsWith("_BULL")) return "BULL";
  if (bucket.endsWith("_BEAR")) return "BEAR";
  return "NEUTRAL";
}

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

function AgentAttributionSummaryInner({ symbol, profileId }: Props) {
  const [windowHours, setWindowHours] = useState(168);
  const [threshold, setThreshold] = useState(0.15);
  const [rows, setRows] = useState<Row[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!symbol) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    api.agentPerformance
      .agentAttributionSummary(symbol, {
        profileId: profileId ?? undefined,
        windowHours,
        threshold,
        limit: 25,
      })
      .then((r) => {
        if (!cancelled) setRows(r);
      })
      .catch((e) => {
        if (!cancelled) setError(e instanceof Error ? e.message : "Failed to load attribution");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [symbol, profileId, windowHours, threshold]);

  const totalCount = useMemo(() => rows.reduce((acc, r) => acc + r.count, 0), [rows]);

  return (
    <div className="bg-zinc-900/50 rounded-lg border border-zinc-800 p-4">
      <div className="flex items-center justify-between mb-3 gap-3 flex-wrap">
        <h3 className="text-sm font-medium text-zinc-300 flex items-center gap-1.5">
          Agent agreement patterns
          <InfoTooltip text="Buckets each closed trade by which agents were bullish, bearish, or neutral at decision time, then shows realized win rate and avg PnL per bucket. Disagreement patterns that consistently win/lose are the strongest signal for re-weighting." />
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
            <span>±</span>
            <select
              className="bg-zinc-800 text-zinc-200 rounded px-1 py-0.5"
              value={threshold}
              onChange={(e) => setThreshold(Number(e.target.value))}
            >
              <option value={0.05}>0.05</option>
              <option value={0.1}>0.10</option>
              <option value={0.15}>0.15</option>
              <option value={0.25}>0.25</option>
            </select>
            <span>threshold</span>
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
          No closed trades with agent context in this window
        </div>
      ) : (
        <>
          <div className="text-[11px] text-zinc-500 mb-2">
            {totalCount} closed trade{totalCount === 1 ? "" : "s"} across {rows.length} pattern{rows.length === 1 ? "" : "s"}
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-zinc-500 border-b border-zinc-800">
                  <th className="text-left py-1.5 pr-2 font-normal">Pattern</th>
                  <th className="text-right py-1.5 px-2 font-normal">Count</th>
                  <th className="text-right py-1.5 px-2 font-normal">Win rate</th>
                  <th className="text-right py-1.5 px-2 font-normal">Avg PnL</th>
                  <th className="text-right py-1.5 px-2 font-normal">Avg $</th>
                  <th className="text-right py-1.5 px-2 font-normal">Conf lift</th>
                  <th className="text-left py-1.5 pl-2 font-normal">W / L / B</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r, i) => {
                  const winRatePct = r.win_rate != null ? r.win_rate * 100 : null;
                  return (
                    <tr key={`${r.pattern}-${i}`} className="border-b border-zinc-800/50">
                      <td className="py-1.5 pr-2 font-mono">
                        {[r.ta_bucket, r.sent_bucket, r.debate_bucket].map((b, idx) => {
                          const stance = stanceFromBucket(b);
                          const prefix = b.split("_")[0];
                          return (
                            <span key={idx}>
                              <span className="text-zinc-500">{prefix}</span>
                              <span className={`${STANCE_COLOR[stance]} font-medium`}>:{stance}</span>
                              {idx < 2 && <span className="text-zinc-600 mx-1">|</span>}
                            </span>
                          );
                        })}
                      </td>
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
                      <td className="py-1.5 px-2 text-right">
                        <span
                          className={
                            r.avg_confidence_lift == null
                              ? "text-zinc-500"
                              : r.avg_confidence_lift > 0
                              ? "text-green-400/80"
                              : r.avg_confidence_lift < 0
                              ? "text-red-400/80"
                              : "text-zinc-500"
                          }
                        >
                          {fmtPct(r.avg_confidence_lift, true)}
                        </span>
                      </td>
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

export const AgentAttributionSummary = memo(AgentAttributionSummaryInner);
