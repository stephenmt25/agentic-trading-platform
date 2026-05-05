"use client";

import { useEffect, useState } from "react";
import { ChevronDown, ChevronUp, Loader2 } from "lucide-react";
import { api } from "@/lib/api/client";

type Detail = Awaited<ReturnType<typeof api.paperTrading.reportDetail>>;
type Trade = Detail["trades"][number];
type BlockedRow = Detail["blocked"]["recent"][number];

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

function fmtTime(iso: string | null): string {
  if (!iso) return "—";
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
  const [expandedBlockedId, setExpandedBlockedId] = useState<string | null>(null);

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
  const blocked = detail.blocked;

  return (
    <div className="space-y-4">
      {/* Summary metrics — 6 cells */}
      {summary && (
        <SectionCard title="Summary" badge={`Day ${detail.report_date}`}>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2">
            <Cell label="Trades" value={String(summary.total_trades)} />
            <Cell label="Win Rate" value={`${(summary.win_rate * 100).toFixed(1)}%`} accent={summary.win_rate >= 0.5 ? "good" : summary.win_rate > 0 ? "bad" : "neutral"} />
            <Cell label="Sharpe" value={summary.sharpe_ratio.toFixed(2)} accent={summary.sharpe_ratio >= 1 ? "good" : summary.sharpe_ratio < 0 ? "bad" : "neutral"} />
            <Cell label="Gross" value={`${summary.gross_pnl >= 0 ? "+" : ""}$${summary.gross_pnl.toFixed(2)}`} accent={summary.gross_pnl >= 0 ? "good" : "bad"} />
            <Cell label="Net" value={`${summary.net_pnl >= 0 ? "+" : ""}$${summary.net_pnl.toFixed(2)}`} accent={summary.net_pnl >= 0 ? "good" : "bad"} />
            <Cell label="Max DD" value={`${(summary.max_drawdown * 100).toFixed(2)}%`} accent="bad" />
          </div>
        </SectionCard>
      )}

      {/* Closed trades */}
      <SectionCard title="Closed trades" badge={`${trades.length}`}>
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
      </SectionCard>

      {/* Blocked decisions — what the engine almost did but rejected */}
      <SectionCard title="Blocked decisions" badge={`${blocked.total}`}>
        {blocked.total === 0 ? (
          <div className="p-4 text-xs text-muted-foreground text-center">
            No blocks recorded on {detail.report_date}.
          </div>
        ) : (
          <>
            {/* Counts by outcome */}
            <div className="flex flex-wrap gap-1.5 mb-2">
              {Object.entries(blocked.counts_by_outcome).map(([outcome, n]) => (
                <span
                  key={outcome}
                  className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded font-mono text-[10px] uppercase border border-amber-500/30 text-amber-400 bg-amber-500/5"
                >
                  {outcome.replace("BLOCKED_", "")}
                  <span className="text-muted-foreground">{n}</span>
                </span>
              ))}
            </div>
            {/* Recent list */}
            <div className="overflow-x-auto max-h-[300px] overflow-y-auto">
              <table className="w-full text-xs font-mono">
                <thead className="sticky top-0 bg-background">
                  <tr className="border-b border-border text-muted-foreground text-[10px] uppercase tracking-wider">
                    <th className="text-left px-3 py-1.5 font-medium">Time</th>
                    <th className="text-left px-3 py-1.5 font-medium">Symbol</th>
                    <th className="text-left px-3 py-1.5 font-medium">Outcome</th>
                    <th className="text-left px-3 py-1.5 font-medium">Reason</th>
                    <th className="px-2 py-1.5 w-6"></th>
                  </tr>
                </thead>
                <tbody>
                  {blocked.recent.map((b) => {
                    const isOpen = expandedBlockedId === b.event_id;
                    const failing = b.gates
                      ? Object.entries(b.gates).find(([, g]) => g?.passed === false)
                      : null;
                    const reason = failing
                      ? `${failing[0]}${failing[1]?.reason ? `: ${failing[1].reason}` : ""}`
                      : b.outcome.replace("BLOCKED_", "").toLowerCase();
                    return (
                      <>
                        <tr
                          key={b.event_id}
                          onClick={() => setExpandedBlockedId(isOpen ? null : b.event_id)}
                          className="border-b border-border/50 hover:bg-accent/20 cursor-pointer"
                        >
                          <td className="px-3 py-1.5 text-muted-foreground tabular-nums">{fmtTime(b.created_at)}</td>
                          <td className="px-3 py-1.5 text-foreground">{b.symbol}</td>
                          <td className="px-3 py-1.5 text-amber-400 text-[10px] uppercase">
                            {b.outcome.replace("BLOCKED_", "")}
                          </td>
                          <td className="px-3 py-1.5 text-muted-foreground truncate max-w-[400px]">{reason}</td>
                          <td className="px-2 py-1.5 text-muted-foreground">
                            {isOpen ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
                          </td>
                        </tr>
                        {isOpen && b.gates && (
                          <tr className="border-b border-border/50 bg-card/20">
                            <td colSpan={5} className="px-3 py-2">
                              <GateChips gates={b.gates} />
                            </td>
                          </tr>
                        )}
                      </>
                    );
                  })}
                </tbody>
              </table>
              {blocked.total > blocked.recent.length && (
                <div className="text-center text-[10px] text-muted-foreground py-2">
                  Showing {blocked.recent.length} most recent of {blocked.total} blocks
                </div>
              )}
            </div>
          </>
        )}
      </SectionCard>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────

function SectionCard({ title, badge, children }: {
  title: string;
  badge?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="border border-border rounded-md overflow-hidden">
      <div className="px-3 py-2 border-b border-border bg-card/30 flex items-baseline gap-2">
        <span className="text-[10px] uppercase tracking-wider font-semibold text-muted-foreground">
          {title}
        </span>
        {badge && <span className="text-[11px] text-muted-foreground tabular-nums">{badge}</span>}
      </div>
      <div className="p-3">{children}</div>
    </div>
  );
}

function Cell({ label, value, accent }: {
  label: string;
  value: string;
  accent?: "good" | "bad" | "neutral";
}) {
  const cls = accent === "good" ? "text-emerald-500"
    : accent === "bad" ? "text-red-500"
    : "text-foreground";
  return (
    <div className="flex flex-col gap-0.5 min-w-0 p-1.5 rounded bg-card/30">
      <span className="text-[10px] uppercase tracking-wider text-muted-foreground font-medium truncate">
        {label}
      </span>
      <span className={`font-mono tabular-nums text-sm font-semibold truncate ${cls}`}>
        {value}
      </span>
    </div>
  );
}

function GateChips({ gates }: { gates: Record<string, DecisionGate> }) {
  return (
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
            {!passed && g?.reason && <span className="ml-1 normal-case lowercase text-[9px] opacity-80">{g.reason}</span>}
          </span>
        );
      })}
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
  const order = trade.order;
  const profileRules = trade.profile_rules as Record<string, unknown> | null;

  return (
    <div className="space-y-2.5 text-[11px]">
      {/* Top row: 4 columns of decision context */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-2">
        {/* Order timeline */}
        <Section title="Order timeline">
          {order ? (
            <div className="space-y-0.5 font-mono">
              <KV k="status" v={order.status ?? "—"} />
              <KV k="exchange" v={order.exchange ?? "—"} />
              <KV k="qty" v={order.quantity != null ? order.quantity.toFixed(6) : "—"} />
              <KV k="intended" v={order.intended_price != null ? `$${order.intended_price.toFixed(2)}` : "—"} />
              <KV k="fill" v={order.fill_price != null ? `$${order.fill_price.toFixed(2)}` : "—"} />
              {order.slippage_pct != null && (
                <KV
                  k="slippage"
                  v={`${order.slippage_pct >= 0 ? "+" : ""}${(order.slippage_pct * 100).toFixed(3)}%`}
                  vCls={
                    order.slippage_pct === 0 ? "text-muted-foreground"
                    : (order.slippage_pct > 0) === (trade.side === "BUY") ? "text-red-400"
                    : "text-emerald-400"
                  }
                />
              )}
              {order.fill_latency_ms != null && (
                <KV k="latency" v={`${order.fill_latency_ms.toFixed(0)} ms`} />
              )}
              <KV k="placed" v={fmtTime(order.created_at)} />
              <KV k="filled" v={fmtTime(order.filled_at)} />
            </div>
          ) : (
            <span className="text-muted-foreground italic">no order recorded</span>
          )}
        </Section>

        {/* Agent attribution */}
        <Section title="Agent attribution">
          {agents ? (
            <div className="space-y-1 font-mono tabular-nums">
              {(["ta", "sentiment", "debate"] as const).map((a) => {
                const det = agents[a];
                if (!det) {
                  return (
                    <div key={a} className="text-muted-foreground/60">
                      {a.toUpperCase()}: <span className="italic">absent</span>
                    </div>
                  );
                }
                const adjCls = (det.adjustment ?? 0) > 0 ? "text-emerald-400"
                  : (det.adjustment ?? 0) < 0 ? "text-red-400"
                  : "text-muted-foreground";
                return (
                  <div key={a} className="flex justify-between gap-2">
                    <span className="text-foreground">{a}</span>
                    <span className="text-muted-foreground">
                      {det.direction ?? "—"} · w {fmtNum(det.weight, 2)} ·{" "}
                      <span className={adjCls}>
                        {(det.adjustment ?? 0) >= 0 ? "+" : ""}{fmtNum(det.adjustment, 3)}
                      </span>
                    </span>
                  </div>
                );
              })}
              {(agents.confidence_before != null || agents.confidence_after != null) && (
                <div className="text-muted-foreground pt-1 mt-1 border-t border-border/40">
                  conf {fmtNum(agents.confidence_before, 3)} → <span className="text-foreground">{fmtNum(agents.confidence_after, 3)}</span>
                </div>
              )}
            </div>
          ) : (
            <span className="text-muted-foreground italic">no agents recorded</span>
          )}
        </Section>

        {/* Gate trace + regime */}
        <Section title="Gate trace">
          {gates ? <GateChips gates={gates} /> : <span className="text-muted-foreground italic">no gate trace</span>}
          {regime && (
            <div className="font-mono text-muted-foreground pt-2 mt-2 border-t border-border/40">
              <div>rule: <span className="text-foreground">{regime.rule_based ?? "—"}</span></div>
              <div>hmm: <span className="text-foreground">{regime.hmm ?? "—"}</span></div>
              <div>resolved: <span className="text-foreground">{regime.resolved ?? "—"}</span>{regime.confidence_multiplier != null && <> · ×{fmtNum(regime.confidence_multiplier, 2)}</>}</div>
            </div>
          )}
        </Section>

        {/* Indicators */}
        <Section title="Indicators">
          {indicators ? (
            <div className="grid grid-cols-2 gap-x-2 gap-y-0.5 font-mono">
              {(["rsi", "macd_line", "signal_line", "histogram", "atr", "adx", "bb_pct_b", "obv", "choppiness"] as const).map((k) => (
                <div key={k} className="flex justify-between gap-1">
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

      {/* Profile rules in effect at decision time */}
      {profileRules && <ProfileRulesPanel rules={profileRules} />}
    </div>
  );
}

function ProfileRulesPanel({ rules }: { rules: Record<string, unknown> }) {
  const direction = rules.direction;
  const logic = rules.logic;
  const baseConf = rules.base_confidence;
  const conditions = (rules.conditions as Array<Record<string, unknown>> | undefined) ?? [];
  const riskLimits = (rules.risk_limits as Record<string, unknown> | undefined) ?? null;

  return (
    <Section title="Profile rules at decision time">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 font-mono">
        <div>
          <div className="text-[10px] uppercase tracking-wider text-muted-foreground mb-1">Strategy</div>
          <div className="space-y-0.5">
            <KV k="direction" v={String(direction ?? "—")} />
            <KV k="logic" v={String(logic ?? "—")} />
            <KV k="base_confidence" v={baseConf != null ? String(baseConf) : "—"} />
            {conditions.length > 0 && (
              <>
                <div className="text-muted-foreground pt-1 mt-1 border-t border-border/40">conditions ({conditions.length}):</div>
                {conditions.map((c, i) => (
                  <div key={i} className="text-foreground pl-2">
                    {String(c.indicator ?? "?")} {String(c.operator ?? "?")} {String(c.value ?? "?")}
                  </div>
                ))}
              </>
            )}
          </div>
        </div>
        <div>
          <div className="text-[10px] uppercase tracking-wider text-muted-foreground mb-1">Risk limits</div>
          {riskLimits ? (
            <div className="space-y-0.5">
              {Object.entries(riskLimits).map(([k, v]) => (
                <KV key={k} k={k} v={String(v)} />
              ))}
            </div>
          ) : (
            <span className="text-muted-foreground italic">no risk_limits captured</span>
          )}
        </div>
      </div>
    </Section>
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

function KV({ k, v, vCls }: { k: string; v: string; vCls?: string }) {
  return (
    <div className="flex justify-between gap-2">
      <span className="text-muted-foreground">{k}</span>
      <span className={`tabular-nums ${vCls ?? "text-foreground"}`}>{v}</span>
    </div>
  );
}
