"use client";

import { useState } from "react";
import { ChevronDown, ChevronRight, Layers } from "lucide-react";
import {
  Bar,
  BarChart,
  Cell,
  ReferenceLine,
  ResponsiveContainer,
  XAxis,
  YAxis,
} from "recharts";

import { Tag } from "@/components/primitives";
import { RiskMeter } from "@/components/trading";
import {
  useDecay,
  useNetOfCost,
  useProfiles,
  useRiskPortfolio,
} from "@/lib/api/hooks";
import { cn } from "@/lib/utils";

/**
 * RiskTruthPanel (FE-W1, locked decision #6) — the three engine-truth
 * surfaces on /risk behind ONE click-to-reveal card with tabs (saved user
 * feedback: progressive disclosure — don't stack panels on-page):
 *
 *   Portfolio — PR4 gross exposure vs budget + cluster/symbol concentration.
 *   Costs     — PR5 per-strategy gross→net waterfall (fees / slippage /
 *               funding attribution). Gross is DERIVED: net_pnl + total_fees.
 *               Slippage and funding are attribution overlays already
 *               embedded in realized PnL (migration 024) — annotation chips,
 *               never re-subtracted.
 *   Decay     — PR7 live-vs-backtest per-profile decay status (the human
 *               companion of EN-W4 auto-deprecation).
 *
 * Default collapsed; the last-open tab is remembered in component state.
 * Each tab mounts its own hook, so nothing polls until revealed and only
 * the visible tab polls (React Query gcTime keeps switching snappy).
 */

type TruthTab = "portfolio" | "costs" | "decay";

const TABS: Array<{ id: TruthTab; label: string }> = [
  { id: "portfolio", label: "Portfolio" },
  { id: "costs", label: "Costs" },
  { id: "decay", label: "Decay" },
];

export function RiskTruthPanel() {
  const [expanded, setExpanded] = useState(false);
  const [tab, setTab] = useState<TruthTab>("portfolio");

  return (
    <section className="flex flex-col gap-2">
      <h2 className="text-[10px] uppercase tracking-wider text-fg-muted num-tabular">
        PORTFOLIO TRUTH
      </h2>
      <div className="rounded-md border border-border-subtle bg-bg-panel">
        <button
          type="button"
          onClick={() => setExpanded((e) => !e)}
          aria-expanded={expanded}
          data-testid="risk-truth-toggle"
          className="w-full flex items-center gap-2.5 px-5 py-3 text-left hover:bg-bg-raised transition-colors rounded-md"
        >
          {expanded ? (
            <ChevronDown className="w-4 h-4 text-fg-muted shrink-0" strokeWidth={1.5} aria-hidden />
          ) : (
            <ChevronRight className="w-4 h-4 text-fg-muted shrink-0" strokeWidth={1.5} aria-hidden />
          )}
          <Layers className="w-4 h-4 text-accent-400 shrink-0" strokeWidth={1.5} aria-hidden />
          <span className="flex-1 min-w-0">
            <span className="block text-[13px] font-semibold text-fg">
              Portfolio risk · net-of-cost · strategy decay
            </span>
            <span className="block text-[11px] text-fg-muted mt-0.5">
              Engine truth panels — exposure vs budget, honest per-strategy
              P&amp;L, live-vs-backtest decay
            </span>
          </span>
        </button>

        {expanded && (
          <div className="border-t border-border-subtle">
            <div
              role="tablist"
              aria-label="Truth panels"
              className="flex items-center gap-1 px-5 pt-3"
            >
              {TABS.map((t) => (
                <button
                  key={t.id}
                  type="button"
                  role="tab"
                  aria-selected={tab === t.id}
                  onClick={() => setTab(t.id)}
                  className={cn(
                    "h-7 px-3 rounded-sm text-[12px] num-tabular transition-colors",
                    tab === t.id
                      ? "bg-bg-raised text-fg font-medium border border-border-strong"
                      : "text-fg-muted hover:text-fg hover:bg-bg-raised border border-transparent"
                  )}
                >
                  {t.label}
                </button>
              ))}
            </div>
            <div className="px-5 py-4">
              {tab === "portfolio" && <PortfolioTab />}
              {tab === "costs" && <CostsTab />}
              {tab === "decay" && <DecayTab />}
            </div>
          </div>
        )}
      </div>
    </section>
  );
}

/* ----------------------------- helpers ------------------------------------ */

/** Display-only parse of a string-encoded Decimal. Never feeds trading math. */
function displayNum(v: string | null | undefined): number {
  const n = parseFloat(v ?? "0");
  return Number.isFinite(n) ? n : 0;
}

function fmtUsd(n: number): string {
  const sign = n < 0 ? "-" : "";
  return `${sign}$${Math.abs(n).toLocaleString(undefined, {
    maximumFractionDigits: 2,
  })}`;
}

function fmtPct(n: number | null | undefined, digits = 1): string {
  if (n === null || n === undefined || !Number.isFinite(n)) return "—";
  return `${(n * 100).toFixed(digits)}%`;
}

function StaleNotice({ what, hint }: { what: string; hint: string }) {
  return (
    <p className="text-[12px] text-fg-muted py-4">
      {what} snapshot stale/absent — {hint}. Values are withheld rather than
      shown as zeros.
    </p>
  );
}

function LoadingNotice() {
  return (
    <div className="py-4 animate-pulse-subtle">
      <div className="h-3 w-40 rounded bg-bg-raised" />
      <div className="h-16 rounded-md bg-bg-raised mt-3" />
    </div>
  );
}

function ErrorNotice({ what }: { what: string }) {
  return (
    <p className="text-[12px] text-danger-500 py-4" role="alert">
      Could not load {what} — backend unreachable or endpoint errored.
    </p>
  );
}

/* ----------------------------- Portfolio tab ------------------------------ */

function PortfolioTab() {
  const { data, isLoading, isError } = useRiskPortfolio();

  if (isLoading) return <LoadingNotice />;
  if (isError || !data) return <ErrorNotice what="portfolio risk" />;
  if (data.stale) {
    return (
      <StaleNotice
        what="Portfolio exposure"
        hint="risk service may be down (key TTL is 120s)"
      />
    );
  }

  const gross = displayNum(data.gross_usd);
  const budget = displayNum(data.gross_budget_usd);
  const capPct = displayNum(data.cluster_cap_pct);
  const clusterCap = capPct * budget;

  const clusters = Object.entries(data.per_cluster)
    .map(([name, v]) => ({ name, notional: displayNum(v) }))
    .sort((a, b) => b.notional - a.notional);
  const symbols = Object.entries(data.per_symbol)
    .map(([symbol, v]) => ({ symbol, notional: displayNum(v) }))
    .sort((a, b) => b.notional - a.notional);

  // Server withheld the per-cluster/per-symbol breakdown (non-operator):
  // say so honestly instead of rendering empty-as-flat.
  const restrictedNote = data.detail_restricted ? (
    <p className="text-[12px] text-fg-muted">
      Breakdown is operator-restricted — aggregate exposure only.
    </p>
  ) : null;

  return (
    <div className="flex flex-col gap-5">
      <div>
        <div className="flex items-center justify-between mb-1.5">
          <span className="text-[12px] uppercase tracking-wider text-fg-muted num-tabular">
            Gross exposure vs budget
          </span>
          <span className="text-[12px] num-tabular text-fg-secondary">
            {fmtUsd(gross)} / {fmtUsd(budget)}
          </span>
        </div>
        <RiskMeter
          kind="custom"
          label="Gross exposure"
          value={gross}
          max={Math.max(budget, 0.0001)}
          format={(v, m) => `${fmtUsd(v)} of ${fmtUsd(m)}`}
        />
      </div>

      <div>
        <div className="flex items-center justify-between mb-1.5">
          <span className="text-[12px] uppercase tracking-wider text-fg-muted num-tabular">
            Cluster concentration
          </span>
          <span className="text-[11px] text-fg-muted num-tabular">
            cap {fmtPct(capPct, 0)} of budget ({fmtUsd(clusterCap)})
          </span>
        </div>
        {clusters.length === 0 ? (
          restrictedNote ?? (
            <p className="text-[12px] text-fg-muted">
              No open exposure — all clusters flat.
            </p>
          )
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {clusters.map((c) => {
              const util = clusterCap > 0 ? c.notional / clusterCap : 0;
              const danger = util >= 0.85;
              const warn = !danger && util >= 0.6;
              return (
                <div
                  key={c.name}
                  className={cn(
                    "rounded-md border p-3 flex flex-col gap-1.5",
                    danger
                      ? "border-danger-700/50"
                      : warn
                        ? "border-warn-700/50"
                        : "border-border-subtle"
                  )}
                >
                  <div className="flex items-baseline justify-between gap-2">
                    <span className="text-[12px] font-mono font-medium text-fg">
                      {c.name}
                    </span>
                    <span className="text-[12px] num-tabular text-fg-secondary">
                      {fmtUsd(c.notional)}
                    </span>
                  </div>
                  <div className="flex items-center justify-between text-[11px] num-tabular text-fg-muted">
                    <span>{fmtPct(budget > 0 ? c.notional / budget : 0)} of budget</span>
                    <span
                      className={cn(
                        danger
                          ? "text-danger-500"
                          : warn
                            ? "text-warn-400"
                            : "text-fg-muted"
                      )}
                    >
                      {fmtPct(util, 0)} of cap
                    </span>
                  </div>
                  <div className="h-1.5 rounded-full bg-bg-raised overflow-hidden">
                    <div
                      className={cn(
                        "h-full rounded-full transition-[width] duration-500",
                        danger
                          ? "bg-danger-500"
                          : warn
                            ? "bg-warn-500"
                            : "bg-bid-500"
                      )}
                      style={{
                        width: `${Math.min(100, Math.max(0, util * 100))}%`,
                      }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      <div>
        <span className="block text-[12px] uppercase tracking-wider text-fg-muted num-tabular mb-1.5">
          Symbol concentration
        </span>
        {symbols.length === 0 ? (
          restrictedNote ?? (
            <p className="text-[12px] text-fg-muted">No open positions.</p>
          )
        ) : (
          <ul className="divide-y divide-border-subtle rounded-md border border-border-subtle">
            {symbols.map((s) => (
              <li
                key={s.symbol}
                className="flex items-center justify-between px-3 py-2 text-[12px] num-tabular"
              >
                <span className="font-mono text-fg">{s.symbol}</span>
                <span className="flex items-baseline gap-3">
                  <span className="text-fg-secondary">{fmtUsd(s.notional)}</span>
                  <span className="text-fg-muted w-14 text-right">
                    {fmtPct(gross > 0 ? s.notional / gross : 0)}
                  </span>
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

/* ----------------------------- Costs tab ---------------------------------- */

function CostsTab() {
  const { data, isLoading, isError } = useNetOfCost(168);
  const { data: profiles } = useProfiles();

  if (isLoading) return <LoadingNotice />;
  if (isError || !data) return <ErrorNotice what="net-of-cost attribution" />;

  const nameOf = new Map((profiles ?? []).map((p) => [p.profile_id, p.name]));
  const rows = data.rows;

  if (rows.length === 0) {
    return (
      <p className="text-[12px] text-fg-muted py-4">
        No closed trades in the last {Math.round(data.window_hours / 24)} days —
        nothing to attribute yet.
      </p>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <p className="text-[11px] text-fg-muted">
        Rolling {Math.round(data.window_hours / 24)}d window. Gross is derived
        (net + fees); slippage/funding are attribution overlays already inside
        realized P&amp;L — shown as chips, never double-subtracted.
      </p>
      {rows.map((r) => (
        <NetOfCostRow
          key={r.profile_id}
          row={r}
          name={nameOf.get(r.profile_id) ?? `${r.profile_id.slice(0, 12)}…`}
        />
      ))}
    </div>
  );
}

interface NetOfCostRowData {
  profile_id: string;
  trade_count: number;
  win_count: number;
  loss_count: number;
  /** String-encoded Decimals from the gateway (Decimal contract) —
   * displayNum() parses for display only. */
  net_pnl: string | null;
  total_fees: string | null;
  total_slippage: string | null;
  total_funding: string | null;
  /** Derived server-side with Decimal: net_pnl + total_fees. */
  gross_pnl: string | null;
  avg_pnl_pct: string | null;
  win_rate: number | null;
  net_negative: boolean;
}

function NetOfCostRow({ row, name }: { row: NetOfCostRowData; name: string }) {
  const net = displayNum(row.net_pnl);
  const fees = displayNum(row.total_fees);
  // The honest accounting (migration 024): gross = net + fees, derived
  // SERVER-side with Decimal (gross_pnl). Slippage and funding are already
  // embedded in realized PnL — attribution only. Display-only parse here.
  const gross = row.gross_pnl != null ? displayNum(row.gross_pnl) : net + fees;

  return (
    <div
      className={cn(
        "rounded-md border p-3 flex flex-col gap-2",
        row.net_negative ? "border-danger-700/50" : "border-border-subtle"
      )}
      data-testid={`netcost-${row.profile_id}`}
    >
      <div className="flex items-center justify-between gap-2 flex-wrap">
        <div className="min-w-0">
          <p className="text-[13px] font-medium text-fg truncate" title={name}>
            {name}
          </p>
          <p className="text-[10px] text-fg-muted font-mono truncate">
            {row.profile_id.slice(0, 12)}…
          </p>
        </div>
        <div className="flex items-center gap-1.5 flex-wrap">
          {row.net_negative && <Tag intent="danger">net-negative</Tag>}
          <Tag intent="neutral">
            {row.trade_count} trades · {fmtPct(row.win_rate, 0)} win
          </Tag>
          <Tag intent="neutral">slippage {fmtUsd(displayNum(row.total_slippage))}</Tag>
          <Tag intent="neutral">funding {fmtUsd(displayNum(row.total_funding))}</Tag>
        </div>
      </div>

      <div className="flex items-center gap-4">
        <div className="flex-1 min-w-0 h-24">
          <GrossToNetWaterfall gross={gross} fees={fees} net={net} />
        </div>
        <dl className="shrink-0 text-[11px] num-tabular grid grid-cols-[auto_auto] gap-x-3 gap-y-1">
          <dt className="text-fg-muted">Gross</dt>
          <dd className="text-right text-fg">{fmtUsd(gross)}</dd>
          <dt className="text-fg-muted">Fees</dt>
          <dd className="text-right text-warn-400">−{fmtUsd(fees)}</dd>
          <dt className="text-fg-muted">Net</dt>
          <dd
            className={cn(
              "text-right font-medium",
              net < 0 ? "text-danger-500" : "text-bid-400"
            )}
          >
            {fmtUsd(net)}
          </dd>
        </dl>
      </div>
    </div>
  );
}

/**
 * Three-column gross→fees→net waterfall. Floating bars are encoded as a
 * transparent stacked base + visible span; everything is shifted by a
 * common offset so mixed-sign values render correctly (Recharts stacks
 * mixed-sign series on opposite axis sides otherwise).
 */
function GrossToNetWaterfall({
  gross,
  fees,
  net,
}: {
  gross: number;
  fees: number;
  net: number;
}) {
  void fees; // fee column is the gross↔net gap by construction
  const cols = [
    {
      name: "Gross",
      lo: Math.min(0, gross),
      hi: Math.max(0, gross),
      fill: "var(--color-neutral-400)",
    },
    {
      name: "Fees",
      lo: Math.min(net, gross),
      hi: Math.max(net, gross),
      fill: "var(--color-warn-500)",
    },
    {
      name: "Net",
      lo: Math.min(0, net),
      hi: Math.max(0, net),
      fill: net < 0 ? "var(--color-danger-500)" : "var(--color-bid-500)",
    },
  ];
  const offset = -Math.min(0, ...cols.map((c) => c.lo));
  const chartData = cols.map((c) => ({
    name: c.name,
    base: c.lo + offset,
    span: c.hi - c.lo,
    fill: c.fill,
  }));

  return (
    <ResponsiveContainer width="100%" height="100%">
      <BarChart data={chartData} margin={{ top: 4, right: 4, bottom: 0, left: 4 }}>
        <XAxis
          dataKey="name"
          tick={{ fontSize: 10, fill: "var(--fg-muted)" }}
          axisLine={false}
          tickLine={false}
        />
        <YAxis hide domain={[0, "dataMax"]} />
        <ReferenceLine y={offset} stroke="var(--border-strong)" strokeDasharray="3 3" />
        <Bar dataKey="base" stackId="w" fill="transparent" isAnimationActive={false} />
        <Bar dataKey="span" stackId="w" isAnimationActive={false} radius={[2, 2, 0, 0]}>
          {chartData.map((entry) => (
            <Cell key={entry.name} fill={entry.fill} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

/* ----------------------------- Decay tab ---------------------------------- */

const DECAY_STATUS_EXPLAINER: Record<string, string> = {
  no_baseline: "No backtest baseline exists for this profile yet.",
  insufficient_live:
    "Not enough live trades in the window for an honest comparison.",
};

function DecayTab() {
  const { data, isLoading, isError } = useDecay();
  const { data: profiles } = useProfiles();

  if (isLoading) return <LoadingNotice />;
  if (isError || !data) return <ErrorNotice what="decay reports" />;
  if (data.stale) {
    return (
      <StaleNotice
        what="Decay"
        hint="analyst service may be down or hasn't completed an assessment pass yet (hourly cadence)"
      />
    );
  }

  const nameOf = new Map((profiles ?? []).map((p) => [p.profile_id, p.name]));

  if (data.profiles.length === 0) {
    return (
      <p className="text-[12px] text-fg-muted py-4">
        No decay reports for your profiles in the latest snapshot.
      </p>
    );
  }

  return (
    <div className="flex flex-col gap-3">
      {data.profiles.map((r) => {
        const muted = r.status === "no_baseline" || r.status === "insufficient_live";
        return (
          <div
            key={r.profile_id}
            className={cn(
              "rounded-md border p-3 flex flex-col gap-2",
              r.decayed ? "border-warn-500/70 bg-warn-500/5" : "border-border-subtle"
            )}
            data-testid={`decay-${r.profile_id}`}
          >
            <div className="flex items-center justify-between gap-2 flex-wrap">
              <div className="min-w-0">
                <p className="text-[13px] font-medium text-fg truncate">
                  {nameOf.get(r.profile_id) ?? `${r.profile_id.slice(0, 12)}…`}
                </p>
                <p className="text-[10px] text-fg-muted font-mono truncate">
                  {r.profile_id.slice(0, 12)}…
                </p>
              </div>
              <Tag intent={r.decayed ? "warn" : muted ? "neutral" : "bid"}>
                {r.status}
              </Tag>
            </div>

            {r.decayed && r.reasons.length > 0 && (
              <ul className="flex flex-col gap-1" aria-label="Decay reasons">
                {r.reasons.map((reason) => (
                  <li
                    key={reason}
                    className="text-[12px] text-warn-400 flex items-start gap-1.5"
                  >
                    <span aria-hidden className="mt-px">▸</span>
                    <span>{reason}</span>
                  </li>
                ))}
              </ul>
            )}
            {muted && (
              <p className="text-[12px] text-fg-muted">
                {DECAY_STATUS_EXPLAINER[r.status]}
              </p>
            )}

            <dl className="grid grid-cols-2 sm:grid-cols-4 gap-x-4 gap-y-1 text-[11px] num-tabular border-t border-border-subtle pt-2">
              <div>
                <dt className="text-fg-muted">Win rate (live / bt)</dt>
                <dd className="text-fg">
                  {fmtPct(r.live_win_rate, 0)}{" "}
                  <span className="text-fg-muted">/ {fmtPct(r.backtest_win_rate, 0)}</span>
                </dd>
              </div>
              <div>
                <dt className="text-fg-muted">Avg return (live / bt)</dt>
                <dd className="text-fg">
                  {fmtPct(r.live_avg_pct, 2)}{" "}
                  <span className="text-fg-muted">/ {fmtPct(r.backtest_avg_return, 2)}</span>
                </dd>
              </div>
              <div>
                <dt className="text-fg-muted">Live trades</dt>
                <dd className="text-fg">{r.live_trades}</dd>
              </div>
              <div>
                <dt className="text-fg-muted">Shadow share</dt>
                <dd className="text-fg">{fmtPct(r.shadow_share, 0)}</dd>
              </div>
            </dl>
          </div>
        );
      })}
    </div>
  );
}

export default RiskTruthPanel;
