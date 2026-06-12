"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { RefreshCw } from "lucide-react";
import { Select, Tag } from "@/components/primitives";
import { Sparkline } from "@/components/data-display";
import { api } from "@/lib/api/client";
import { useGateAnalytics } from "@/lib/api/hooks";
import { cn } from "@/lib/utils";

interface AttributionTabProps {
  profileId: string;
}

const WINDOW_HOURS = 168; // 7 days

interface WeightHistoryPoint {
  symbol: string;
  agent_name: string;
  weight: number;
  ewma_accuracy: number;
  sample_count: number;
  recorded_at: string;
}

interface AgentAttributionPattern {
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

interface ClosedTrade {
  profile_id: string;
  symbol: string;
}

export function AttributionTab({ profileId }: AttributionTabProps) {
  const [symbols, setSymbols] = useState<string[]>([]);
  const [symbol, setSymbol] = useState<string | null>(null);
  const [loadingSymbols, setLoadingSymbols] = useState(true);

  // Discover which symbols this profile has traded.
  useEffect(() => {
    let cancelled = false;
    api.audit
      .closedTrades({ limit: 500 })
      .then((trades) => {
        if (cancelled) return;
        const counts = new Map<string, number>();
        for (const t of trades as ClosedTrade[]) {
          if (t.profile_id !== profileId) continue;
          counts.set(t.symbol, (counts.get(t.symbol) ?? 0) + 1);
        }
        const sorted = [...counts.entries()]
          .sort((a, b) => b[1] - a[1])
          .map(([s]) => s);
        setSymbols(sorted);
        if (sorted.length > 0 && !symbol) setSymbol(sorted[0]);
        setLoadingSymbols(false);
      })
      .catch(() => {
        if (!cancelled) setLoadingSymbols(false);
      });
    return () => {
      cancelled = true;
    };
  }, [profileId, symbol]);

  return (
    <div className="flex flex-col h-full min-h-0">
      <div className="shrink-0 px-4 py-3 border-b border-border-subtle flex items-center justify-between gap-3">
        <div className="flex flex-col gap-0.5">
          <p className="text-[10px] uppercase tracking-wider text-fg-muted">
            Symbol scope
          </p>
          <p className="text-[11px] text-fg-muted">
            Attribution endpoints are symbol-axis; pick a symbol this profile
            has traded.
          </p>
        </div>
        {loadingSymbols ? (
          <span className="text-[11px] text-fg-muted">Loading symbols…</span>
        ) : symbols.length === 0 ? (
          <Tag intent="warn">no traded symbols</Tag>
        ) : (
          <Select
            density="compact"
            options={symbols.map((s) => ({ value: s, label: s }))}
            value={symbol ?? undefined}
            onValueChange={(v) => setSymbol(v)}
            placeholder="Select symbol…"
            className="min-w-[160px]"
          />
        )}
      </div>

      <div className="flex-1 min-h-0 overflow-auto">
        {!symbol ? (
          <EmptyState />
        ) : (
          <div className="px-4 py-4 flex flex-col gap-5">
            <GateEfficacySection symbol={symbol} profileId={profileId} />
            <PerAgentSection symbol={symbol} profileId={profileId} />
            <WeightEvolutionSection symbol={symbol} />
          </div>
        )}
      </div>
    </div>
  );
}

/* ----------------------- Gate efficacy ----------------------- */

function GateEfficacySection({
  symbol,
  profileId,
}: {
  symbol: string;
  profileId: string;
}) {
  // FE-W2.1: shared ["gateAnalytics", symbol, profile, limit] query — the
  // hook bakes the 60s refetchInterval this section used to wire by hand.
  const gateQuery = useGateAnalytics(symbol, { profileId, limit: 500 });
  const data = gateQuery.data ?? null;
  const loading = gateQuery.isFetching;
  const err = gateQuery.error
    ? gateQuery.error instanceof Error
      ? gateQuery.error.message
      : "Failed to load gate analytics"
    : null;
  const load = () => gateQuery.refetch();

  const rows = useMemo(() => {
    if (!data) return [];
    return Object.entries(data.gate_details)
      .map(([name, d]) => {
        const total = d.passed + d.blocked;
        const passRate = total > 0 ? d.passed / total : null;
        const topReason = Object.entries(d.reasons).sort(
          (a, b) => b[1] - a[1]
        )[0];
        return {
          name,
          passed: d.passed,
          blocked: d.blocked,
          total,
          pass_rate: passRate,
          top_reason: topReason ? topReason[0] : null,
          top_reason_count: topReason ? topReason[1] : 0,
        };
      })
      .sort((a, b) => b.blocked - a.blocked);
  }, [data]);

  return (
    <SectionFrame
      title="Gate efficacy"
      subtitle={
        data
          ? `${data.total_decisions.toLocaleString()} decisions evaluated · last 500`
          : undefined
      }
      onRefresh={load}
      loading={loading}
      err={err}
    >
      {!loading && rows.length === 0 ? (
        <p className="text-[12px] text-fg-muted px-1">
          No gate activity recorded for {symbol} on this profile.
        </p>
      ) : (
        <table className="w-full text-[12px] num-tabular border-separate border-spacing-0">
          <thead>
            <tr>
              <Th align="left">Gate</Th>
              <Th align="right">Pass</Th>
              <Th align="right">Block</Th>
              <Th align="right">Pass %</Th>
              <Th align="left">Top block reason</Th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.name} className="hover:bg-bg-rowhover">
                <Td>
                  <span className="font-mono text-fg">{r.name}</span>
                </Td>
                <Td align="right">
                  <span className="font-mono text-bid-300">{r.passed}</span>
                </Td>
                <Td align="right">
                  <span className="font-mono text-danger-500">
                    {r.blocked}
                  </span>
                </Td>
                <Td align="right">
                  <span className="font-mono text-fg-secondary">
                    {r.pass_rate === null
                      ? "—"
                      : `${(r.pass_rate * 100).toFixed(0)}%`}
                  </span>
                </Td>
                <Td>
                  <span className="font-mono text-fg-muted truncate">
                    {r.top_reason
                      ? `${r.top_reason} (${r.top_reason_count})`
                      : "—"}
                  </span>
                </Td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </SectionFrame>
  );
}

/* ----------------------- Per-agent contribution ----------------------- */

function PerAgentSection({
  symbol,
  profileId,
}: {
  symbol: string;
  profileId: string;
}) {
  const [rows, setRows] = useState<AgentAttributionPattern[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await api.agentPerformance.agentAttributionSummary(symbol, {
        profileId,
        windowHours: WINDOW_HOURS,
        threshold: 0.05,
      });
      setRows(r);
      setErr(null);
    } catch (e) {
      setErr(
        e instanceof Error ? e.message : "Failed to load agent attribution"
      );
    } finally {
      setLoading(false);
    }
  }, [symbol, profileId]);

  useEffect(() => {
    load();
  }, [load]);

  const ordered = useMemo(
    () => [...rows].sort((a, b) => b.count - a.count).slice(0, 12),
    [rows]
  );

  return (
    <SectionFrame
      title="Per-agent contribution"
      subtitle={`Win rate × avg P&L by (TA / Sent / Debate) stance · last ${Math.round(WINDOW_HOURS / 24)}d`}
      onRefresh={load}
      loading={loading}
      err={err}
    >
      {!loading && ordered.length === 0 ? (
        <p className="text-[12px] text-fg-muted px-1">
          Need closed trades on {symbol} for this profile to compute
          attribution.
        </p>
      ) : (
        <table className="w-full text-[12px] num-tabular border-separate border-spacing-0">
          <thead>
            <tr>
              <Th align="left">Pattern (TA · Sent · Debate)</Th>
              <Th align="right">Trades</Th>
              <Th align="right">Win rate</Th>
              <Th align="right">Avg PnL %</Th>
              <Th align="right">Avg PnL $</Th>
              <Th align="right">Conf. lift</Th>
            </tr>
          </thead>
          <tbody>
            {ordered.map((r) => (
              <tr key={r.pattern} className="hover:bg-bg-rowhover">
                <Td>
                  <span className="font-mono text-fg">
                    {fmtPattern(r.ta_bucket, r.sent_bucket, r.debate_bucket)}
                  </span>
                </Td>
                <Td align="right">
                  <span className="font-mono text-fg-secondary">
                    {r.count}
                  </span>
                </Td>
                <Td align="right">
                  <WinRateCell rate={r.win_rate} />
                </Td>
                <Td align="right">
                  <PnlCell value={r.avg_pnl_pct} kind="pct" />
                </Td>
                <Td align="right">
                  <PnlCell value={r.avg_pnl_usd} kind="usd" />
                </Td>
                <Td align="right">
                  <span className="font-mono text-fg-muted">
                    {r.avg_confidence_lift === null
                      ? "—"
                      : r.avg_confidence_lift.toFixed(3)}
                  </span>
                </Td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </SectionFrame>
  );
}

/* ----------------------- Weight evolution ----------------------- */

function WeightEvolutionSection({ symbol }: { symbol: string }) {
  const [points, setPoints] = useState<WeightHistoryPoint[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await api.agentPerformance.weightHistory(symbol, { limit: 200 });
      setPoints(r);
      setErr(null);
    } catch (e) {
      setErr(
        e instanceof Error ? e.message : "Failed to load weight history"
      );
    } finally {
      setLoading(false);
    }
  }, [symbol]);

  useEffect(() => {
    load();
  }, [load]);

  // Group by agent_name, sorted chronologically.
  const byAgent = useMemo(() => {
    const m = new Map<
      string,
      { weight: number; ewma: number; recorded_at: string }[]
    >();
    for (const p of points) {
      const arr = m.get(p.agent_name) ?? [];
      arr.push({
        weight: p.weight,
        ewma: p.ewma_accuracy,
        recorded_at: p.recorded_at,
      });
      m.set(p.agent_name, arr);
    }
    // ascending by time for sparkline
    for (const arr of m.values()) {
      arr.sort((a, b) => Date.parse(a.recorded_at) - Date.parse(b.recorded_at));
    }
    return m;
  }, [points]);

  return (
    <SectionFrame
      title="Weight evolution"
      subtitle="Agent weight + accuracy over time · symbol-scoped"
      pendingNote="profile-scoped filter pending (backend endpoint is symbol-only)"
      onRefresh={load}
      loading={loading}
      err={err}
    >
      {!loading && byAgent.size === 0 ? (
        <p className="text-[12px] text-fg-muted px-1">
          No weight history recorded for {symbol} yet.
        </p>
      ) : (
        <ul className="flex flex-col gap-1.5">
          {[...byAgent.entries()].map(([name, series]) => {
            const last = series[series.length - 1];
            const first = series[0];
            const delta = last && first ? last.weight - first.weight : 0;
            return (
              <li
                key={name}
                className="rounded-md border border-border-subtle bg-bg-canvas px-3 py-2 flex items-center justify-between gap-3"
              >
                <div className="min-w-0 flex-1 flex flex-col">
                  <span className="font-mono text-fg text-[12px]">{name}</span>
                  <span className="text-[11px] text-fg-muted num-tabular">
                    weight {last?.weight.toFixed(3) ?? "—"}
                    {first && last && (
                      <span
                        className={cn(
                          "ml-1.5",
                          delta > 0
                            ? "text-bid-300"
                            : delta < 0
                              ? "text-danger-500"
                              : "text-fg-muted"
                        )}
                      >
                        ({delta > 0 ? "+" : ""}
                        {delta.toFixed(3)})
                      </span>
                    )}
                    {" · "}
                    accuracy {last?.ewma.toFixed(3) ?? "—"} · {series.length}{" "}
                    pts
                  </span>
                </div>
                <Sparkline
                  values={series.map((s) => s.weight)}
                  width={120}
                  height={28}
                  tone={delta >= 0 ? "bid" : "ask"}
                />
              </li>
            );
          })}
        </ul>
      )}
    </SectionFrame>
  );
}

/* ----------------------- Shared ----------------------- */

function SectionFrame({
  title,
  subtitle,
  pendingNote,
  onRefresh,
  loading,
  err,
  children,
}: {
  title: string;
  subtitle?: string;
  pendingNote?: string;
  onRefresh?: () => void;
  loading?: boolean;
  err: string | null;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-md border border-border-subtle bg-bg-panel/60 flex flex-col">
      <header className="flex items-start justify-between gap-3 px-3 py-2.5 border-b border-border-subtle">
        <div className="min-w-0">
          <h3 className="text-[12px] font-medium text-fg">{title}</h3>
          {subtitle && (
            <p className="text-[11px] text-fg-muted mt-0.5">{subtitle}</p>
          )}
          {pendingNote && (
            <p className="text-[11px] text-warn-400 mt-1 inline-flex items-center gap-1.5">
              <Tag intent="warn">Pending</Tag>
              <span>{pendingNote}</span>
            </p>
          )}
        </div>
        {onRefresh && (
          <button
            type="button"
            onClick={onRefresh}
            aria-label="Refresh"
            className="h-7 w-7 shrink-0 rounded-md flex items-center justify-center text-fg-muted hover:text-fg hover:bg-bg-raised"
          >
            <RefreshCw
              className={cn(
                "w-3 h-3",
                loading && "animate-spin will-change-transform"
              )}
              strokeWidth={1.5}
              aria-hidden
            />
          </button>
        )}
      </header>
      <div className="px-3 py-2.5">
        {err ? (
          <p className="text-[12px] text-danger-500">
            Couldn&rsquo;t load: {err}
          </p>
        ) : (
          children
        )}
      </div>
    </section>
  );
}

function Th({
  children,
  align = "left",
}: {
  children?: React.ReactNode;
  align?: "left" | "right";
}) {
  return (
    <th
      className={cn(
        "px-2 h-7 text-[10px] uppercase tracking-wider font-medium text-fg-muted",
        "border-b border-border-subtle",
        align === "right" ? "text-right" : "text-left"
      )}
    >
      {children}
    </th>
  );
}

function Td({
  children,
  align = "left",
}: {
  children: React.ReactNode;
  align?: "left" | "right";
}) {
  return (
    <td
      className={cn(
        "px-2 h-7 border-b border-border-subtle/60",
        align === "right" ? "text-right" : "text-left"
      )}
    >
      {children}
    </td>
  );
}

function WinRateCell({ rate }: { rate: number | null }) {
  if (rate === null) return <span className="text-fg-muted font-mono">—</span>;
  const cls =
    rate >= 0.55
      ? "text-bid-300"
      : rate < 0.45
        ? "text-danger-500"
        : "text-fg";
  return (
    <span className={cn("font-mono", cls)}>{(rate * 100).toFixed(1)}%</span>
  );
}

function PnlCell({
  value,
  kind,
}: {
  value: number | null;
  kind: "pct" | "usd";
}) {
  if (value === null) return <span className="text-fg-muted font-mono">—</span>;
  const cls =
    value > 0 ? "text-bid-300" : value < 0 ? "text-danger-500" : "text-fg";
  const sign = value > 0 ? "+" : "";
  const formatted =
    kind === "pct"
      ? `${sign}${(value * 100).toFixed(2)}%`
      : `${sign}$${value.toFixed(2)}`;
  return <span className={cn("font-mono", cls)}>{formatted}</span>;
}

function fmtPattern(ta: string, sent: string, debate: string): string {
  return `${ta} · ${sent} · ${debate}`;
}

function EmptyState() {
  return (
    <div className="m-6 max-w-md mx-auto text-center flex flex-col items-center gap-3">
      <Tag intent="warn">Pending</Tag>
      <p className="text-[14px] text-fg">No closed trades yet</p>
      <p className="text-[12px] text-fg-muted">
        Attribution requires at least one closed trade for this profile. Open
        the Decisions tab to see what the engine is evaluating in the
        meantime.
      </p>
    </div>
  );
}
