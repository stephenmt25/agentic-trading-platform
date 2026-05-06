"use client";

import { useEffect, useState, useCallback, Fragment } from "react";
import { Loader2, TrendingUp, TrendingDown, ChevronRight, ChevronDown, X } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api/client";

interface Position {
  position_id: string;
  profile_id: string;
  symbol: string;
  side: "BUY" | "SELL";
  entry_price: string;
  quantity: string;
  entry_fee?: string | null;
  opened_at: string;
  status: string;
  decision_event_id?: string | null;
  unrealized_net_pnl?: number | null;
  unrealized_gross_pnl?: number | null;
  unrealized_pct_return?: number | null;
  notional?: string | null;
  profile_notional?: string | null;
  allocation_used_pct?: number | null;
  mark_price?: string | null;
  stop_loss_price?: string | null;
  stop_loss_pct?: string | null;
  take_profit_price?: string | null;
  take_profit_pct?: string | null;
}

interface ChainData {
  decision: Record<string, unknown> | null;
  order: Record<string, unknown> | null;
  position: Record<string, unknown> | null;
  closed_trade: Record<string, unknown> | null;
}

function ageMin(opened_at: string): number {
  return Math.floor((Date.now() - new Date(opened_at).getTime()) / 60000);
}

function fmtNum(s?: string | number | null, digits = 2): string {
  if (s === null || s === undefined) return "—";
  const n = typeof s === "number" ? s : parseFloat(s);
  return Number.isFinite(n) ? n.toFixed(digits) : String(s);
}

function fmtUsd(s?: string | number | null): string {
  if (s === null || s === undefined) return "—";
  const n = typeof s === "number" ? s : parseFloat(s);
  if (!Number.isFinite(n)) return "—";
  if (Math.abs(n) >= 1000) return `$${n.toFixed(0)}`;
  return `$${n.toFixed(2)}`;
}

function fmtPct(p?: number | null, digits = 1): string {
  if (typeof p !== "number" || !Number.isFinite(p)) return "—";
  return `${(p * 100).toFixed(digits)}%`;
}

function distancePct(mark?: string | null, target?: string | null): number | null {
  if (!mark || !target) return null;
  const m = parseFloat(mark);
  const t = parseFloat(target);
  if (!Number.isFinite(m) || !Number.isFinite(t) || m === 0) return null;
  return (t - m) / m;
}

function ExpandedRow({ position }: { position: Position }) {
  const [chain, setChain] = useState<ChainData | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    if (!position.decision_event_id) {
      setLoading(false);
      return;
    }
    api.audit.chain(position.decision_event_id)
      .then((c) => { if (!cancelled) setChain(c); })
      .catch((e: unknown) => { if (!cancelled) setErr(e instanceof Error ? e.message : "lookup failed"); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [position.decision_event_id]);

  const decision = (chain?.decision ?? {}) as Record<string, unknown>;
  const regime = (decision.regime as { state?: string } | string | undefined);
  const regimeLabel = typeof regime === "string" ? regime : regime?.state ?? "—";
  const agents = decision.agents as Record<string, { score?: number; confidence?: number; weight?: number }> | undefined;
  const gates = decision.gates as Record<string, { passed?: boolean; reason?: string }> | undefined;
  const rationale = decision.rationale as string | undefined;
  const finalScore = decision.final_score as number | undefined;

  const sortedAgents = agents
    ? Object.entries(agents)
        .map(([name, v]) => ({
          name,
          score: typeof v?.score === "number" ? v.score : null,
          weight: typeof v?.weight === "number" ? v.weight : null,
        }))
        .sort((a, b) => Math.abs(b.score ?? 0) - Math.abs(a.score ?? 0))
        .slice(0, 6)
    : [];

  return (
    <tr className="bg-card/40">
      <td colSpan={10} className="px-4 py-3">
        {loading ? (
          <div className="flex items-center gap-2 text-[11px] text-muted-foreground">
            <Loader2 className="w-3 h-3 animate-spin" /> Loading decision lineage…
          </div>
        ) : err ? (
          <div className="text-[11px] text-amber-500">Could not load lineage: {err}</div>
        ) : !position.decision_event_id ? (
          <div className="text-[11px] text-muted-foreground">
            No decision event linked to this position (likely a manual or legacy fill).
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-[11px]">
            {/* Why we entered */}
            <div className="space-y-1.5">
              <div className="text-[10px] uppercase tracking-wider text-muted-foreground">Why we entered</div>
              <div className="space-y-0.5">
                <div className="text-muted-foreground">
                  Regime: <span className="font-mono text-foreground">{regimeLabel}</span>
                </div>
                {typeof finalScore === "number" && (
                  <div className="text-muted-foreground">
                    Final score: <span className="font-mono text-foreground">{finalScore.toFixed(3)}</span>
                  </div>
                )}
                {rationale && (
                  <div className="text-muted-foreground/90 italic mt-1 line-clamp-3">{rationale}</div>
                )}
              </div>
            </div>

            {/* Top contributing agents */}
            <div className="space-y-1.5">
              <div className="text-[10px] uppercase tracking-wider text-muted-foreground">Top agents</div>
              {sortedAgents.length === 0 ? (
                <div className="text-muted-foreground/70">no agent scores recorded</div>
              ) : (
                <table className="w-full">
                  <tbody>
                    {sortedAgents.map((a) => (
                      <tr key={a.name}>
                        <td className="font-mono text-foreground py-0.5">{a.name}</td>
                        <td className={`text-right font-mono tabular-nums py-0.5 ${
                          (a.score ?? 0) > 0 ? "text-emerald-500" :
                          (a.score ?? 0) < 0 ? "text-red-500" : "text-muted-foreground"
                        }`}>
                          {a.score !== null ? a.score.toFixed(3) : "—"}
                        </td>
                        <td className="text-right font-mono tabular-nums text-muted-foreground/70 py-0.5">
                          {a.weight !== null ? `w${a.weight.toFixed(2)}` : ""}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>

            {/* Gates */}
            <div className="space-y-1.5">
              <div className="text-[10px] uppercase tracking-wider text-muted-foreground">Gates passed</div>
              {gates && Object.keys(gates).length > 0 ? (
                <ul className="space-y-0.5">
                  {Object.entries(gates).map(([name, g]) => (
                    <li key={name} className="flex justify-between gap-2">
                      <span className="font-mono">{name}</span>
                      <span className={g?.passed ? "text-emerald-500" : "text-red-500"}>
                        {g?.passed ? "pass" : g?.reason ? `block: ${g.reason}` : "block"}
                      </span>
                    </li>
                  ))}
                </ul>
              ) : (
                <div className="text-muted-foreground/70">no gate detail recorded</div>
              )}
              {position.decision_event_id && (
                <div className="pt-1 text-muted-foreground/60 truncate">
                  decision: <span className="font-mono">{position.decision_event_id.slice(0, 8)}…</span>
                </div>
              )}
            </div>
          </div>
        )}
      </td>
    </tr>
  );
}

function CloseDialog({
  position,
  onConfirm,
  onCancel,
  busy,
}: {
  position: Position;
  onConfirm: () => void;
  onCancel: () => void;
  busy: boolean;
}) {
  const isLong = position.side === "BUY";
  const net = position.unrealized_net_pnl;
  const pct = position.unrealized_pct_return;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-background/80 backdrop-blur-sm" onClick={onCancel}>
      <div
        className="bg-card border border-border rounded-lg shadow-xl p-5 max-w-md w-full mx-4 space-y-3"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-foreground">Close position?</h3>
          <button onClick={onCancel} className="text-muted-foreground hover:text-foreground" aria-label="Cancel">
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="space-y-1.5 text-xs font-mono">
          <div className="flex justify-between">
            <span className="text-muted-foreground">Symbol</span>
            <span className="text-foreground">{position.symbol}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted-foreground">Side / Qty</span>
            <span className={isLong ? "text-emerald-500" : "text-red-500"}>
              {isLong ? "long" : "short"} {fmtNum(position.quantity, 4)}
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted-foreground">Entry → Mark</span>
            <span className="text-foreground">
              ${fmtNum(position.entry_price)} → {position.mark_price ? `$${fmtNum(position.mark_price)}` : "—"}
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted-foreground">Unrealized</span>
            <span className={
              typeof net !== "number" ? "text-muted-foreground" :
              net > 0 ? "text-emerald-500" : net < 0 ? "text-red-500" : "text-foreground"
            }>
              {typeof net === "number" ? `${net >= 0 ? "+" : ""}$${net.toFixed(2)}` : "—"}
              {typeof pct === "number" ? ` (${pct >= 0 ? "+" : ""}${(pct * 100).toFixed(2)}%)` : ""}
            </span>
          </div>
        </div>

        <div className="text-[10px] text-amber-500/90 leading-relaxed">
          Closes the internal position record at the latest mark and records the realized PnL.
          Does not submit an exchange order — flatten on the exchange separately if running live.
        </div>

        <div className="flex gap-2 justify-end pt-1">
          <button
            onClick={onCancel}
            disabled={busy}
            className="px-3 py-1.5 text-xs rounded border border-border hover:bg-accent disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            onClick={onConfirm}
            disabled={busy}
            className="px-3 py-1.5 text-xs rounded bg-red-500/90 text-white hover:bg-red-500 disabled:opacity-50 inline-flex items-center gap-1.5"
          >
            {busy && <Loader2 className="w-3 h-3 animate-spin" />}
            Close position
          </button>
        </div>
      </div>
    </div>
  );
}

export function PositionsPanel({ profileId }: { profileId?: string | null }) {
  const [positions, setPositions] = useState<Position[]>([]);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [closeTarget, setCloseTarget] = useState<Position | null>(null);
  const [closing, setClosing] = useState(false);

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

  const handleClose = useCallback(async () => {
    if (!closeTarget) return;
    setClosing(true);
    try {
      const res = await api.positions.close(closeTarget.position_id);
      const net = parseFloat(res.net_pnl_pre_tax);
      const sign = Number.isFinite(net) && net >= 0 ? "+" : "";
      toast.success(
        `Closed ${closeTarget.symbol} at $${fmtNum(res.exit_price)} — net ${sign}$${Number.isFinite(net) ? net.toFixed(2) : "—"}`,
      );
      setPositions((prev) => prev.filter((p) => p.position_id !== closeTarget.position_id));
      setCloseTarget(null);
    } catch (e: unknown) {
      toast.error(`Close failed: ${e instanceof Error ? e.message : "unknown error"}`);
    } finally {
      setClosing(false);
    }
  }, [closeTarget]);

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
      if (p.notional) {
        const n = parseFloat(p.notional);
        if (Number.isFinite(n)) acc.notional += n;
      }
      return acc;
    },
    { net: 0, notional: 0 },
  );

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs">
        <thead>
          <tr className="text-[10px] uppercase tracking-wider text-muted-foreground border-b border-border">
            <th className="w-6"></th>
            <th className="text-left font-medium py-2 px-2">Symbol</th>
            <th className="text-left font-medium py-2 px-2">Side</th>
            <th className="text-right font-medium py-2 px-2">Qty</th>
            <th className="text-right font-medium py-2 px-2">Entry / Mark</th>
            <th className="text-right font-medium py-2 px-2" title="Position notional ($) and percentage of profile capital allocated">
              Notional / Alloc
            </th>
            <th className="text-right font-medium py-2 px-2" title="Stop-loss and take-profit price levels with distance from mark">
              SL / TP
            </th>
            <th className="text-right font-medium py-2 px-2">Unreal. ($/%)</th>
            <th className="text-right font-medium py-2 px-2">Age</th>
            <th className="font-medium py-2 px-2"></th>
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
            const isExpanded = expanded === p.position_id;

            const distSL = distancePct(p.mark_price, p.stop_loss_price);
            const distTP = distancePct(p.mark_price, p.take_profit_price);

            return (
              <Fragment key={p.position_id}>
                <tr
                  className="border-b border-border/40 hover:bg-accent/30 transition-colors cursor-pointer"
                  onClick={() => setExpanded(isExpanded ? null : p.position_id)}
                >
                  <td className="px-1 text-muted-foreground">
                    {isExpanded ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
                  </td>
                  <td className="py-2 px-2 font-mono text-foreground">{p.symbol}</td>
                  <td className="py-2 px-2">
                    <span className={`inline-flex items-center gap-1 text-[11px] font-mono ${isLong ? "text-emerald-500" : "text-red-500"}`}>
                      {isLong ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
                      {isLong ? "long" : "short"}
                    </span>
                  </td>
                  <td className="py-2 px-2 text-right font-mono tabular-nums text-foreground">
                    {fmtNum(p.quantity, 4)}
                  </td>
                  <td className="py-2 px-2 text-right font-mono tabular-nums text-foreground">
                    <div>${fmtNum(p.entry_price)}</div>
                    <div className="text-[10px] text-muted-foreground">
                      mark {p.mark_price ? `$${fmtNum(p.mark_price)}` : "—"}
                    </div>
                  </td>
                  <td className="py-2 px-2 text-right font-mono tabular-nums text-foreground">
                    <div>{fmtUsd(p.notional)}</div>
                    <div className="text-[10px] text-muted-foreground">
                      {fmtPct(p.allocation_used_pct)} of {fmtUsd(p.profile_notional)}
                    </div>
                  </td>
                  <td className="py-2 px-2 text-right font-mono tabular-nums">
                    <div className="text-red-500/90">
                      SL {p.stop_loss_price ? `$${fmtNum(p.stop_loss_price)}` : "—"}
                      {distSL !== null && (
                        <span className="text-muted-foreground/70 ml-1">
                          ({(distSL * 100).toFixed(2)}%)
                        </span>
                      )}
                    </div>
                    <div className="text-emerald-500/90 text-[10px]">
                      TP {p.take_profit_price ? `$${fmtNum(p.take_profit_price)}` : "—"}
                      {distTP !== null && (
                        <span className="text-muted-foreground/70 ml-1">
                          (+{(distTP * 100).toFixed(2)}%)
                        </span>
                      )}
                    </div>
                  </td>
                  <td className={`py-2 px-2 text-right font-mono tabular-nums ${pnlColor}`}>
                    <div>
                      {typeof net === "number"
                        ? `${net >= 0 ? "+" : ""}$${net.toFixed(2)}`
                        : "—"}
                    </div>
                    <div className="text-[10px]">
                      {typeof pct === "number"
                        ? `${pct >= 0 ? "+" : ""}${(pct * 100).toFixed(2)}%`
                        : "—"}
                    </div>
                  </td>
                  <td className="py-2 px-2 text-right font-mono tabular-nums text-muted-foreground">
                    {ageMinutes < 60 ? `${ageMinutes}m` : `${(ageMinutes / 60).toFixed(1)}h`}
                  </td>
                  <td className="py-2 px-2 text-right">
                    <button
                      onClick={(e) => { e.stopPropagation(); setCloseTarget(p); }}
                      className="text-[10px] uppercase tracking-wider px-2 py-1 rounded border border-red-500/30 text-red-500 hover:bg-red-500/10 transition-colors"
                      title="Close this position at the latest mark price"
                    >
                      Close
                    </button>
                  </td>
                </tr>
                {isExpanded && <ExpandedRow position={p} />}
              </Fragment>
            );
          })}
        </tbody>
        {positions.some((p) => typeof p.unrealized_net_pnl === "number") && (
          <tfoot>
            <tr className="border-t border-border bg-card/30">
              <td colSpan={5} className="py-2 px-2 text-right text-[10px] uppercase tracking-wider text-muted-foreground font-medium">
                Total
              </td>
              <td className="py-2 px-2 text-right font-mono tabular-nums font-semibold text-foreground">
                {fmtUsd(totals.notional)}
              </td>
              <td className="py-2 px-2"></td>
              <td
                className={`py-2 px-2 text-right font-mono tabular-nums font-semibold ${
                  totals.net > 0 ? "text-emerald-500" : totals.net < 0 ? "text-red-500" : "text-foreground"
                }`}
              >
                {totals.net >= 0 ? "+" : ""}${totals.net.toFixed(2)}
              </td>
              <td className="py-2 px-2"></td>
              <td className="py-2 px-2"></td>
            </tr>
          </tfoot>
        )}
      </table>
      {closeTarget && (
        <CloseDialog
          position={closeTarget}
          onConfirm={handleClose}
          onCancel={() => { if (!closing) setCloseTarget(null); }}
          busy={closing}
        />
      )}
    </div>
  );
}
