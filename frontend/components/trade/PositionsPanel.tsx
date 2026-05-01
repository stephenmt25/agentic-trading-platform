"use client";

import { useEffect, useState, useCallback } from "react";
import { Loader2, TrendingUp, TrendingDown } from "lucide-react";
import { api } from "@/lib/api/client";

interface Position {
  position_id: string;
  symbol: string;
  side: "BUY" | "SELL";
  entry_price: string;
  quantity: string;
  opened_at: string;
  status: string;
  unrealized_net_pnl?: number | null;
  unrealized_pct_return?: number | null;
}

function ageMin(opened_at: string): number {
  return Math.floor((Date.now() - new Date(opened_at).getTime()) / 60000);
}

function fmtPrice(s: string): string {
  const n = parseFloat(s);
  return Number.isFinite(n) ? n.toFixed(2) : s;
}

export function PositionsPanel({ profileId }: { profileId?: string | null }) {
  const [positions, setPositions] = useState<Position[]>([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      const opts: { status: "open"; profileId?: string } = { status: "open" };
      if (profileId) opts.profileId = profileId;
      const rows = await api.positions.list(opts);
      setPositions(rows as Position[]);
    } catch {
      // best-effort; empty list is acceptable
    } finally {
      setLoading(false);
    }
  }, [profileId]);

  useEffect(() => {
    load();
    const t = setInterval(load, 15_000);
    return () => clearInterval(t);
  }, [load]);

  if (loading) {
    return (
      <div className="flex justify-center py-6">
        <Loader2 className="w-4 h-4 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (positions.length === 0) {
    return (
      <div className="text-center py-8 px-4 space-y-2">
        <p className="text-xs text-muted-foreground">No open positions.</p>
        <p className="text-[11px] text-muted-foreground/70 max-w-md mx-auto">
          Positions appear here when an APPROVED signal becomes a fill. Most signals are filtered
          upstream by the abstention and circuit-breaker gates — that&apos;s the engine being
          paranoid, not broken. Watch the Decision Feed to see what got blocked and why.
        </p>
      </div>
    );
  }

  const totals = positions.reduce(
    (acc, p) => {
      if (typeof p.unrealized_net_pnl === "number") acc.net += p.unrealized_net_pnl;
      return acc;
    },
    { net: 0 },
  );

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs">
        <thead>
          <tr className="text-[10px] uppercase tracking-wider text-muted-foreground border-b border-border">
            <th className="text-left font-medium py-2 px-2">Symbol</th>
            <th className="text-left font-medium py-2 px-2">Side</th>
            <th className="text-right font-medium py-2 px-2">Qty</th>
            <th className="text-right font-medium py-2 px-2">Entry</th>
            <th className="text-right font-medium py-2 px-2">Unreal.</th>
            <th className="text-right font-medium py-2 px-2">%</th>
            <th className="text-right font-medium py-2 px-2">Age</th>
          </tr>
        </thead>
        <tbody>
          {positions.map((p) => {
            const isLong = p.side === "BUY";
            const ageMinutes = ageMin(p.opened_at);
            const net = p.unrealized_net_pnl;
            const pct = p.unrealized_pct_return;
            const pnlColor =
              typeof net !== "number" ? "text-muted-foreground/50" :
              net > 0 ? "text-emerald-500" :
              net < 0 ? "text-red-500" :
              "text-foreground";
            return (
              <tr key={p.position_id} className="border-b border-border/40 hover:bg-accent/30 transition-colors">
                <td className="py-2 px-2 font-mono text-foreground">{p.symbol}</td>
                <td className="py-2 px-2">
                  <span className={`inline-flex items-center gap-1 text-[11px] font-mono ${isLong ? "text-emerald-500" : "text-red-500"}`}>
                    {isLong ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
                    {isLong ? "long" : "short"}
                  </span>
                </td>
                <td className="py-2 px-2 text-right font-mono tabular-nums text-foreground">{fmtPrice(p.quantity)}</td>
                <td className="py-2 px-2 text-right font-mono tabular-nums text-foreground">${fmtPrice(p.entry_price)}</td>
                <td className={`py-2 px-2 text-right font-mono tabular-nums ${pnlColor}`}>
                  {typeof net === "number"
                    ? `${net >= 0 ? "+" : ""}$${net.toFixed(2)}`
                    : "—"}
                </td>
                <td className={`py-2 px-2 text-right font-mono tabular-nums ${pnlColor}`}>
                  {typeof pct === "number"
                    ? `${pct >= 0 ? "+" : ""}${(pct * 100).toFixed(2)}%`
                    : "—"}
                </td>
                <td className="py-2 px-2 text-right font-mono tabular-nums text-muted-foreground">
                  {ageMinutes < 60 ? `${ageMinutes}m` : `${(ageMinutes / 60).toFixed(1)}h`}
                </td>
              </tr>
            );
          })}
        </tbody>
        {positions.some((p) => typeof p.unrealized_net_pnl === "number") && (
          <tfoot>
            <tr className="border-t border-border bg-card/30">
              <td colSpan={4} className="py-2 px-2 text-right text-[10px] uppercase tracking-wider text-muted-foreground font-medium">
                Total unrealized
              </td>
              <td
                className={`py-2 px-2 text-right font-mono tabular-nums font-semibold ${
                  totals.net > 0 ? "text-emerald-500" : totals.net < 0 ? "text-red-500" : "text-foreground"
                }`}
                colSpan={3}
              >
                {totals.net >= 0 ? "+" : ""}${totals.net.toFixed(2)}
              </td>
            </tr>
          </tfoot>
        )}
      </table>
    </div>
  );
}
