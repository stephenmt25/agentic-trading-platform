"use client";

import { memo, useEffect, useMemo, useState } from "react";
import { InfoTooltip } from "@/components/ui/InfoTooltip";
import { api } from "@/lib/api/client";
import { Loader2 } from "lucide-react";

const REASON_COLOR: Record<string, string> = {
  stop_loss: "#ef4444",
  take_profit: "#22c55e",
  time_exit: "#f59e0b",
  manual: "#8b5cf6",
  opposing_signal: "#3b82f6",
  unknown: "#6b7280",
};

const WINDOW_OPTIONS: Array<{ label: string; hours: number }> = [
  { label: "24h", hours: 24 },
  { label: "7d", hours: 168 },
  { label: "30d", hours: 720 },
];

interface Row {
  close_reason: string;
  regime?: string;
  count: number;
  win_count: number;
  loss_count: number;
  breakeven_count: number;
  win_rate: number | null;
  avg_pnl_pct: number | null;
  median_holding_s: number | null;
}

interface Props {
  symbol?: string;
  profileId?: string | null;
}

function fmtHolding(seconds: number | null): string {
  if (seconds == null || seconds <= 0) return "—";
  if (seconds < 60) return `${seconds}s`;
  const m = Math.floor(seconds / 60);
  if (m < 60) return `${m}m`;
  const h = Math.floor(m / 60);
  const rem = m % 60;
  return rem ? `${h}h ${rem}m` : `${h}h`;
}

function fmtPct(value: number | null, signed = false): string {
  if (value == null) return "—";
  const pct = value * 100;
  const formatted = pct.toFixed(2);
  return signed && pct > 0 ? `+${formatted}%` : `${formatted}%`;
}

function CloseReasonPanelInner({ symbol, profileId }: Props) {
  const [windowHours, setWindowHours] = useState(168);
  const [groupByRegime, setGroupByRegime] = useState(false);
  const [rows, setRows] = useState<Row[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    api.audit
      .closeReasons({
        symbol,
        profileId: profileId ?? undefined,
        windowHours,
        groupByRegime,
      })
      .then((r) => {
        if (!cancelled) setRows(r);
      })
      .catch((e) => {
        if (!cancelled) setError(e instanceof Error ? e.message : "Failed to load close reasons");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [symbol, profileId, windowHours, groupByRegime]);

  const totalCount = useMemo(() => rows.reduce((acc, r) => acc + r.count, 0), [rows]);

  return (
    <div className="bg-zinc-900/50 rounded-lg border border-zinc-800 p-4">
      <div className="flex items-center justify-between mb-3 gap-3 flex-wrap">
        <h3 className="text-sm font-medium text-zinc-300 flex items-center gap-1.5">
          Close-reason taxonomy
          <InfoTooltip text="Of every closed trade in this window, which exit fired and how did it perform? Stop-loss-heavy means the strategy is exiting on noise; time-exit-heavy means signals don't pay off within the holding cap." />
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
            <input
              type="checkbox"
              checked={groupByRegime}
              onChange={(e) => setGroupByRegime(e.target.checked)}
              className="accent-primary"
            />
            split by regime
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
          No closed trades in this window
        </div>
      ) : (
        <>
          <div className="text-[11px] text-zinc-500 mb-2">{totalCount} closed trade{totalCount === 1 ? "" : "s"}</div>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-zinc-500 border-b border-zinc-800">
                  <th className="text-left py-1.5 pr-2 font-normal">Reason</th>
                  {groupByRegime && <th className="text-left py-1.5 pr-2 font-normal">Regime</th>}
                  <th className="text-right py-1.5 px-2 font-normal">Count</th>
                  <th className="text-right py-1.5 px-2 font-normal">Win rate</th>
                  <th className="text-right py-1.5 px-2 font-normal">Avg PnL</th>
                  <th className="text-right py-1.5 px-2 font-normal">Median hold</th>
                  <th className="text-left py-1.5 pl-2 font-normal">W / L / B</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r, i) => {
                  const color = REASON_COLOR[r.close_reason] ?? REASON_COLOR.unknown;
                  const winRatePct = r.win_rate != null ? r.win_rate * 100 : null;
                  return (
                    <tr key={`${r.close_reason}-${r.regime ?? "_"}-${i}`} className="border-b border-zinc-800/50">
                      <td className="py-1.5 pr-2">
                        <span className="inline-flex items-center gap-1.5">
                          <span className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: color }} />
                          <span className="capitalize text-zinc-300">{r.close_reason.replace(/_/g, " ")}</span>
                        </span>
                      </td>
                      {groupByRegime && <td className="py-1.5 pr-2 text-zinc-400">{r.regime ?? "—"}</td>}
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
                      <td className="py-1.5 px-2 text-right text-zinc-400">{fmtHolding(r.median_holding_s)}</td>
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

export const CloseReasonPanel = memo(CloseReasonPanelInner);
