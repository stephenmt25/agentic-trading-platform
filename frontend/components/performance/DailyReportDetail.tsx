"use client";

import { useEffect, useState } from "react";
import { ChevronDown, ChevronUp, Loader2 } from "lucide-react";
import { api } from "@/lib/api/client";

type Detail = Awaited<ReturnType<typeof api.paperTrading.reportDetail>>;
type Trade = Detail["trades"][number];

interface AgentDetail {
  score?: number | null;
  weight?: number;
  adjustment?: number;
  direction?: string;
}

interface DecisionAgents {
  ta?: AgentDetail;
  sentiment?: AgentDetail;
  debate?: AgentDetail;
  confidence_before?: number;
  confidence_after?: number;
}

interface DecisionGate {
  passed?: boolean;
  reason?: string;
}

interface DecisionRegime {
  rule_based?: string | null;
  hmm?: string | null;
  resolved?: string | null;
  confidence_multiplier?: number;
}

interface DecisionIndicators {
  rsi?: number;
  macd_line?: number;
  signal_line?: number;
  histogram?: number;
  atr?: number;
  adx?: number | null;
  bb_pct_b?: number | null;
  obv?: number | null;
  choppiness?: number | null;
}

function fmtTime(iso: string): string {
  return new Date(iso).toLocaleTimeString([], {
    hour: "2-digit", minute: "2-digit", second: "2-digit",
  });
}

function fmtDuration(seconds: number): string {
  if (seconds < 60) return `${seconds}s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m`;
  if (seconds < 86400) return `${(seconds / 3600).toFixed(1)}h`;
  return `${(seconds / 86400).toFixed(1)}d`;
}

function fmtNum(v: number | undefined | null, digits = 3): string {
  if (v == null || Number.isNaN(v)) return "—";
  return v.toFixed(digits);
}

interface Props {
  date: string;
}

export function DailyReportDetail({ date }: Props) {
  const [detail, setDetail] = useState<Detail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedTradeId, setExpandedTradeId] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    api.paperTrading
      .reportDetail(date)
      .then((d) => {
        if (!cancelled) setDetail(d);
      })
      .catch((e) => {
        if (!cancelled) setError(e instanceof Error ? e.message : "Failed to load report detail");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [date]);

  if (loading) {
    return (
      <div className="flex items-center gap-2 p-4 text-xs text-muted-foreground">
        <Loader2 className="w-3.5 h-3.5 animate-spin" />
        Loading report…
      </div>
    );
  }
  if (error) {
    return <div className="p-4 text-xs text-red-400">{error}</div>;
  }
  if (!detail) return null;

  const summary = detail.summary;
  const trades = detail.trades;

  return (
    <div className="space-y-3">
      {/* Summary metrics — same 6-cell grid the row used to show, but wider
          to accommodate the trades section below. */}
      {summary && (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2 p-2.5 border border-border rounded-md bg-card/30">
          <Cell label="Trades" value={String(summary.total_trades)} />
          <Cell label="Win Rate" value={`${(summary.win_rate * 100).toFixed(1)}%`} accent={summary.win_rate >= 0.5 ? "good" : summary.win_rate > 0 ? "bad" : "neutral"} />
          <Cell label="Sharpe" value={summary.sharpe_ratio.toFixed(2)} accent={summary.sharpe_ratio >= 1 ? "good" : summary.sharpe_ratio < 0 ? "bad" : "neutral"} />
          <Cell label="Gross" value={`${summary.gross_pnl >= 0 ? "+" : ""}$${summary.gross_pnl.toFixed(2)}`} accent={summary.gross_pnl >= 0 ? "good" : "bad"} />
          <Cell label="Net" value={`${summary.net_pnl >= 0 ? "+" : ""}$${summary.net_pnl.toFixed(2)}`} accent={summary.net_pnl >= 0 ? "good" : "bad"} />
          <Cell label="Max DD" value={`${(summary.max_drawdown * 100).toFixed(2)}%`} accent="bad" />
        </div>
      )}

      {/* Trades for the day */}
      <div className="border border-border rounded-md overflow-hidden">
        <div className="px-3 py-2 border-b border-border bg-card/30 flex items-baseline gap-2">
          <span className="text-[10px] uppercase tracking-wider font-semibold text-muted-foreground">
            Closed trades
          </span>
          <span className="text-[11px] text-muted-foreground tabular-nums">{trades.length}</span>
        </div>
        {trades.length === 0 ? (
          <div className="p-4 text-xs text-muted-foreground text-center">
            No closed trades on {detail.report_date}.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-xs font-mono">
              <thead>
                <tr className="border-b border-border text-muted-foreground text-[10px] uppercase tracking-wider">
                  <th className="text-left px-3 py-1.5 font-medium">Closed</th>
                  <th className="text-left px-3 py-1.5 font-medium">Symbol</th>
                  <th className="text-left px-3 py-1.5 font-medium">Side</th>
                  <th className="text-right px-3 py-1.5 font-medium">Entry</th>
                  <th className="text-right px-3 py-1.5 font-medium">Exit</th>
                  <th className="text-right px-3 py-1.5 font-medium">Hold</th>
                  <th className="text-right px-3 py-1.5 font-medium">P&amp;L</th>
                  <th className="text-right px-3 py-1.5 font-medium">P&amp;L %</th>
                  <th className="text-left px-3 py-1.5 font-medium">Reason</th>
                  <th className="text-left px-3 py-1.5 font-medium">Outcome</th>
                  <th className="px-2 py-1.5 w-6"></th>
                </tr>
              </thead>
              <tbody>
                {trades.map((t) => {
                  const isOpen = expandedTradeId === t.position_id;
                  const pnlClass =
                    t.realized_pnl > 0 ? "text-emerald-400"
                      : t.realized_pnl < 0 ? "text-red-400"
                      : "text-muted-foreground";
                  return (
                    <ExpandableTradeRow
                      key={t.position_id}
                      trade={t}
                      isOpen={isOpen}
                      pnlClass={pnlClass}
                      onToggle={() =>
                        setExpandedTradeId(isOpen ? null : t.position_id)
                      }
                    />
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────

function Cell({ label, value, accent }: {
  label: string;
  value: string;
  accent?: "good" | "bad" | "neutral";
}) {
  const cls = accent === "good" ? "text-emerald-500"
    : accent === "bad" ? "text-red-500"
    : "text-foreground";
  return (
    <div className="flex flex-col gap-0.5 min-w-0">
      <span className="text-[10px] uppercase tracking-wider text-muted-foreground font-medium truncate">
        {label}
      </span>
      <span className={`font-mono tabular-nums text-sm font-semibold truncate ${cls}`}>
        {value}
      </span>
    </div>
  );
}

function ExpandableTradeRow({ trade, isOpen, pnlClass, onToggle }: {
  trade: Trade;
  isOpen: boolean;
  pnlClass: string;
  onToggle: () => void;
}) {
  const outcomeCls =
    trade.outcome === "win" ? "text-emerald-400"
    : trade.outcome === "loss" ? "text-red-400"
    : "text-muted-foreground";
  return (
    <>
      <tr
        onClick={onToggle}
        className="border-b border-border/50 hover:bg-accent/30 cursor-pointer"
      >
        <td className="px-3 py-1.5 text-muted-foreground tabular-nums">{fmtTime(trade.closed_at)}</td>
        <td className="px-3 py-1.5 text-foreground">{trade.symbol}</td>
        <td className="px-3 py-1.5">
          <span className={trade.side === "BUY" ? "text-emerald-400" : "text-red-400"}>{trade.side}</span>
        </td>
        <td className="px-3 py-1.5 text-right text-foreground tabular-nums">${trade.entry_price.toFixed(2)}</td>
        <td className="px-3 py-1.5 text-right text-foreground tabular-nums">${trade.exit_price.toFixed(2)}</td>
        <td className="px-3 py-1.5 text-right text-muted-foreground tabular-nums">{fmtDuration(trade.holding_duration_s)}</td>
        <td className={`px-3 py-1.5 text-right tabular-nums ${pnlClass}`}>
          {trade.realized_pnl >= 0 ? "+" : ""}${trade.realized_pnl.toFixed(2)}
        </td>
        <td className={`px-3 py-1.5 text-right tabular-nums ${pnlClass}`}>
          {trade.realized_pnl_pct >= 0 ? "+" : ""}
          {(trade.realized_pnl_pct * 100).toFixed(2)}%
        </td>
        <td className="px-3 py-1.5 text-muted-foreground">{trade.close_reason}</td>
        <td className={`px-3 py-1.5 uppercase ${outcomeCls}`}>{trade.outcome}</td>
        <td className="px-2 py-1.5 text-muted-foreground">
          {isOpen ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
        </td>
      </tr>
      {isOpen && (
        <tr className="border-b border-border/50 bg-card/20">
          <td colSpan={11} className="px-3 py-3">
            <DecisionPanel trade={trade} />
          </td>
        </tr>
      )}
    </>
  );
}

function DecisionPanel({ trade }: { trade: Trade }) {
  const agents = (trade.decision_agents as DecisionAgents | null) ?? null;
  const gates = (trade.decision_gates as Record<string, DecisionGate> | null) ?? null;
  const regime = (trade.decision_regime as DecisionRegime | null) ?? null;
  const indicators = (trade.decision_indicators as DecisionIndicators | null) ?? null;

  if (!trade.decision_event_id && !agents && !gates && !indicators) {
    return (
      <div className="text-[11px] text-muted-foreground italic">
        No decision lineage recorded for this trade (decision row missing or pre-PR1).
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-3 text-[11px]">
      {/* Agents */}
      <Section title="Agent attribution">
        {agents ? (
          <div className="space-y-1">
            {(["ta", "sentiment", "debate"] as const).map((a) => {
              const det = agents[a];
              if (!det) return (
                <div key={a} className="text-muted-foreground/60">
                  {a.toUpperCase()}: <span className="italic">absent</span>
                </div>
              );
              const adjCls = (det.adjustment ?? 0) > 0 ? "text-emerald-400"
                : (det.adjustment ?? 0) < 0 ? "text-red-400"
                : "text-muted-foreground";
              return (
                <div key={a} className="font-mono tabular-nums">
                  <span className="text-foreground">{a.toUpperCase().padEnd(9)}</span>
                  <span className="text-muted-foreground"> dir={det.direction ?? "—"} </span>
                  <span className="text-muted-foreground">score={fmtNum(det.score, 3)} </span>
                  <span className="text-muted-foreground">w={fmtNum(det.weight, 2)} </span>
                  <span className={adjCls}>
                    {(det.adjustment ?? 0) >= 0 ? "+" : ""}{fmtNum(det.adjustment, 3)}
                  </span>
                </div>
              );
            })}
            {(agents.confidence_before != null || agents.confidence_after != null) && (
              <div className="font-mono text-muted-foreground pt-1 mt-1 border-t border-border/40">
                conf {fmtNum(agents.confidence_before, 3)} → <span className="text-foreground">{fmtNum(agents.confidence_after, 3)}</span>
              </div>
            )}
          </div>
        ) : (
          <span className="text-muted-foreground italic">no agents recorded</span>
        )}
      </Section>

      {/* Gates */}
      <Section title="Gate trace">
        {gates ? (
          <div className="flex flex-wrap gap-1">
            {Object.entries(gates).map(([name, g]) => {
              const passed = g?.passed === true;
              const cls = passed
                ? "border-emerald-500/30 text-emerald-400 bg-emerald-500/5"
                : "border-red-500/30 text-red-400 bg-red-500/5";
              return (
                <span
                  key={name}
                  title={g?.reason ?? (passed ? "passed" : "blocked")}
                  className={`inline-flex items-center px-1.5 py-0.5 rounded font-mono text-[10px] uppercase border ${cls}`}
                >
                  {name} {passed ? "✓" : "✕"}
                </span>
              );
            })}
          </div>
        ) : (
          <span className="text-muted-foreground italic">no gate trace</span>
        )}
        {regime && (
          <div className="font-mono text-muted-foreground pt-2">
            regime: rule={regime.rule_based ?? "—"} · hmm={regime.hmm ?? "—"} · resolved=
            <span className="text-foreground">{regime.resolved ?? "—"}</span>
            {regime.confidence_multiplier != null && (
              <> · ×{fmtNum(regime.confidence_multiplier, 2)}</>
            )}
          </div>
        )}
      </Section>

      {/* Indicators */}
      <Section title="Indicators at decision">
        {indicators ? (
          <div className="grid grid-cols-2 gap-x-3 gap-y-0.5 font-mono">
            {(["rsi", "macd_line", "signal_line", "histogram", "atr", "adx", "bb_pct_b", "obv", "choppiness"] as const).map((k) => (
              <div key={k} className="flex justify-between gap-2">
                <span className="text-muted-foreground">{k}</span>
                <span className="tabular-nums text-foreground">
                  {fmtNum(indicators[k] as number | undefined, k === "obv" ? 0 : 4)}
                </span>
              </div>
            ))}
          </div>
        ) : (
          <span className="text-muted-foreground italic">no indicator snapshot</span>
        )}
      </Section>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="border border-border/50 rounded p-2 bg-background/40">
      <div className="text-[9px] uppercase tracking-wider text-muted-foreground font-semibold mb-1.5">{title}</div>
      {children}
    </div>
  );
}
