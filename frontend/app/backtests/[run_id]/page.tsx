"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import {
  ArrowLeft,
  Loader2,
  AlertTriangle,
  Workflow,
  Info,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";
import { Button, Tag } from "@/components/primitives";
import {
  KeyValue,
  Sparkline,
  Pill,
  StatusDot,
  Table,
  type SortDirection,
  type TableColumn,
} from "@/components/data-display";
import { PnLBadge } from "@/components/trading";
import { api, type ProfileResponse } from "@/lib/api/client";
import { cn } from "@/lib/utils";

interface SimulatedTrade {
  entry_time: string;
  exit_time: string | null;
  direction: "BUY" | "SELL";
  entry_price: number;
  exit_price: number | null;
  pnl_pct: number;
}

interface BacktestPayload {
  job_id: string;
  status: string;
  symbol?: string;
  profile_id?: string | null;
  total_trades?: number;
  win_rate?: number;
  avg_return?: number;
  max_drawdown?: number;
  sharpe?: number;
  profit_factor?: number;
  equity_curve?: number[];
  trades?: SimulatedTrade[];
  start_date?: string | null;
  end_date?: string | null;
  timeframe?: string | null;
  created_by?: string | null;
  error?: string;
}

const TRADES_PAGE_SIZE = 50;

function toNumber(v: unknown, fallback = 0): number {
  if (typeof v === "number") return Number.isFinite(v) ? v : fallback;
  if (typeof v === "string") {
    const n = parseFloat(v);
    return Number.isFinite(n) ? n : fallback;
  }
  return fallback;
}

function shortJob(jobId: string): string {
  return jobId.slice(0, 7);
}

function formatDate(s: string | null | undefined): string {
  if (!s) return "—";
  return s.slice(0, 10);
}

function formatRange(start: string | null | undefined, end: string | null | undefined): string {
  const a = formatDate(start);
  const b = formatDate(end);
  if (a === "—" && b === "—") return "—";
  return `${a} → ${b}`;
}

function daysBetween(start: string | null | undefined, end: string | null | undefined): string {
  if (!start || !end) return "";
  const ms = Date.parse(end) - Date.parse(start);
  if (!Number.isFinite(ms) || ms <= 0) return "";
  return `${Math.round(ms / 86_400_000)} days`;
}

function holdingDuration(entry: string, exit: string | null): string {
  if (!exit) return "—";
  const ms = Date.parse(exit) - Date.parse(entry);
  if (!Number.isFinite(ms) || ms <= 0) return "—";
  const m = Math.round(ms / 60_000);
  if (m < 60) return `${m}m`;
  const h = Math.floor(m / 60);
  const rem = m % 60;
  if (h < 24) return rem ? `${h}h ${rem}m` : `${h}h`;
  const d = Math.floor(h / 24);
  const hRem = h % 24;
  return hRem ? `${d}d ${hRem}h` : `${d}d`;
}

function statusPill(status: string) {
  if (status === "completed") {
    return (
      <Pill intent="bid" icon={<StatusDot state="live" size={6} />}>
        Done
      </Pill>
    );
  }
  if (status === "running") {
    return (
      <Pill intent="accent" icon={<StatusDot state="live" size={6} pulse />}>
        Running
      </Pill>
    );
  }
  if (status === "queued") {
    return (
      <Pill intent="neutral" icon={<StatusDot state="idle" size={6} />}>
        Queued
      </Pill>
    );
  }
  return (
    <Pill intent="ask" icon={<StatusDot state="error" size={6} />}>
      Failed
    </Pill>
  );
}

/**
 * /backtests/{run_id} — run detail. Per surface spec
 * docs/design/05-surface-specs/04-backtesting-analytics.md §2.
 *
 * Compositional only — Chart primitive is spec'd at
 * docs/design/04-component-specs/chart.md but not yet implemented.
 * Equity curve, trade distribution, and regime breakdown render as
 * Sparkline + Pending placeholders until the Chart component lands.
 *
 * Backend gaps surfaced inline as `<Tag intent="warn">Pending</Tag>`
 * (matches 6.1 / 6.2a pattern):
 *   - Sortino, avgR (R-multiples), regime breakdown, per-agent
 *     attribution, canvas-as-run snapshot, per-trade exit reason +
 *     decision-event link.
 */
export default function BacktestRunDetailPage() {
  const params = useParams<{ run_id: string }>();
  const router = useRouter();
  const runId = decodeURIComponent(params.run_id);

  const [payload, setPayload] = useState<BacktestPayload | null>(null);
  const [profile, setProfile] = useState<ProfileResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [sortKey, setSortKey] = useState<string>("entry_time");
  const [sortDir, setSortDir] = useState<SortDirection>("desc");
  const [page, setPage] = useState(0);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.backtest.result(runId);
      const cast = res as unknown as BacktestPayload;
      setPayload(cast);
      const profileId = cast.profile_id;
      if (profileId) {
        api.profiles
          .list()
          .then((all) => {
            const found = all.find((p) => p.profile_id === profileId);
            if (found) setProfile(found);
          })
          .catch(() => {});
      }
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Failed to load run";
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, [runId]);

  useEffect(() => {
    load();
  }, [load]);

  const trades = useMemo(() => payload?.trades ?? [], [payload]);
  const equity = useMemo(() => payload?.equity_curve ?? [], [payload]);

  const roi = useMemo(() => {
    if (equity.length < 2) return null;
    const start = equity[0];
    const end = equity[equity.length - 1];
    if (!Number.isFinite(start) || start === 0) return null;
    return (end - start) / start;
  }, [equity]);

  const winLoss = useMemo(() => {
    if (!trades.length) return { wins: 0, losses: 0, breakeven: 0 };
    let wins = 0;
    let losses = 0;
    let breakeven = 0;
    for (const t of trades) {
      if (t.pnl_pct > 0) wins++;
      else if (t.pnl_pct < 0) losses++;
      else breakeven++;
    }
    return { wins, losses, breakeven };
  }, [trades]);

  const sortedTrades = useMemo(() => {
    const copy = [...trades];
    copy.sort((a, b) => {
      const av = (a as unknown as Record<string, unknown>)[sortKey];
      const bv = (b as unknown as Record<string, unknown>)[sortKey];
      let cmp = 0;
      if (typeof av === "number" && typeof bv === "number") cmp = av - bv;
      else cmp = String(av ?? "").localeCompare(String(bv ?? ""));
      return sortDir === "asc" ? cmp : -cmp;
    });
    return copy;
  }, [trades, sortKey, sortDir]);

  const pageCount = Math.max(1, Math.ceil(sortedTrades.length / TRADES_PAGE_SIZE));
  const safePage = Math.min(page, pageCount - 1);
  const pagedTrades = useMemo(
    () =>
      sortedTrades.slice(
        safePage * TRADES_PAGE_SIZE,
        safePage * TRADES_PAGE_SIZE + TRADES_PAGE_SIZE
      ),
    [sortedTrades, safePage]
  );

  const profileName = profile?.name || (payload?.profile_id?.slice(0, 7) ?? "—");
  const isCompleted = payload?.status === "completed";

  const tradeColumns: TableColumn<SimulatedTrade>[] = useMemo(
    () => [
      {
        key: "entry_time",
        header: "Entry",
        sortable: true,
        render: (t) => (
          <span className="font-mono text-fg-secondary num-tabular text-[12px]">
            {t.entry_time?.replace("T", " ").slice(0, 19) ?? "—"}
          </span>
        ),
      },
      {
        key: "direction",
        header: "Side",
        render: (t) => (
          <Tag intent={t.direction === "BUY" ? "bid" : "ask"}>{t.direction}</Tag>
        ),
      },
      {
        key: "entry_price",
        header: "Entry px",
        numeric: true,
        sortable: true,
        render: (t) => (
          <span className="font-mono text-fg num-tabular">
            {Number.isFinite(t.entry_price) ? t.entry_price.toLocaleString(undefined, { maximumFractionDigits: 6 }) : "—"}
          </span>
        ),
      },
      {
        key: "exit_price",
        header: "Exit px",
        numeric: true,
        sortable: true,
        render: (t) =>
          t.exit_price != null ? (
            <span className="font-mono text-fg num-tabular">
              {t.exit_price.toLocaleString(undefined, { maximumFractionDigits: 6 })}
            </span>
          ) : (
            <span className="text-fg-muted">open</span>
          ),
      },
      {
        key: "pnl_pct",
        header: "Return",
        numeric: true,
        sortable: true,
        render: (t) =>
          t.exit_price != null ? (
            <PnLBadge value={t.pnl_pct * 100} mode="pct" hideArrow />
          ) : (
            <span className="text-fg-muted">—</span>
          ),
      },
      {
        key: "holding",
        header: "Held",
        align: "right",
        render: (t) => (
          <span className="font-mono text-fg-secondary num-tabular text-[12px]">
            {holdingDuration(t.entry_time, t.exit_time)}
          </span>
        ),
      },
    ],
    []
  );

  return (
    <div data-mode="cool" className="flex flex-col h-full bg-bg-canvas text-fg">
      <header className="flex items-start justify-between gap-4 border-b border-border-subtle px-6 py-4">
        <div className="min-w-0">
          <div className="flex items-center gap-2 text-[12px] text-fg-muted">
            <Link
              href="/backtests"
              className="inline-flex items-center gap-1 hover:text-fg transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent-500 rounded-sm"
            >
              <ArrowLeft className="w-3 h-3" strokeWidth={1.5} />
              Backtests
            </Link>
            <span aria-hidden>/</span>
            <span className="font-mono text-fg-secondary">#{shortJob(runId)}</span>
            {payload?.status && <span className="ml-1">{statusPill(payload.status)}</span>}
          </div>
          <h1 className="text-[18px] font-semibold tracking-tight text-fg mt-1.5 truncate">
            {profileName}
            <span className="text-fg-muted font-normal ml-2 text-[14px]">
              {payload?.symbol || ""}
            </span>
          </h1>
          {payload && (
            <p className="text-[12px] text-fg-muted mt-0.5 num-tabular">
              {formatRange(payload.start_date, payload.end_date)}
              {daysBetween(payload.start_date, payload.end_date) && (
                <span> · {daysBetween(payload.start_date, payload.end_date)}</span>
              )}
              {payload.timeframe && <span> · {payload.timeframe}</span>}
              {/* The result payload doesn't carry an authoritative created_at
                  (only created_by). Skip "run X ago" here; surfaced on list. */}
            </p>
          )}
        </div>

        <div className="flex items-center gap-2 shrink-0">
          <CanvasSnapshotButton profileId={payload?.profile_id ?? null} runId={runId} />
        </div>
      </header>

      <div className="flex-1 min-h-0 overflow-auto">
        {loading && (
          <div className="mx-6 mt-6 rounded-md border border-border-subtle bg-bg-panel p-6 flex items-center gap-3">
            <Loader2 className="w-4 h-4 text-fg-muted animate-spin" aria-hidden />
            <span className="text-[13px] text-fg-muted">Loading run #{shortJob(runId)}…</span>
          </div>
        )}

        {!loading && error && (
          <div
            role="alert"
            className="mx-6 mt-6 rounded-md border border-danger-700/40 bg-danger-700/10 p-4 flex items-start gap-3 text-[13px] text-danger-500"
          >
            <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" strokeWidth={1.5} aria-hidden />
            <div className="flex-1">
              <p className="font-medium">Could not load run.</p>
              <p className="text-fg-muted mt-0.5">{error}</p>
            </div>
            <Button intent="secondary" size="sm" onClick={load}>
              Retry
            </Button>
            <Button intent="secondary" size="sm" onClick={() => router.push("/backtests")}>
              Back to list
            </Button>
          </div>
        )}

        {!loading && !error && payload && !isCompleted && (
          <NotCompletedPanel payload={payload} onRetry={load} />
        )}

        {!loading && !error && payload && isCompleted && (
          <div className="px-6 py-6 flex flex-col gap-6">
            <HeadlineMetrics
              roi={roi}
              winRate={toNumber(payload.win_rate)}
              maxDrawdown={toNumber(payload.max_drawdown)}
              sharpe={toNumber(payload.sharpe)}
              profitFactor={toNumber(payload.profit_factor)}
              avgReturn={toNumber(payload.avg_return)}
              totalTrades={payload.total_trades ?? trades.length}
              winLoss={winLoss}
            />

            <EquityCurveSection equity={equity} roi={roi} />

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <DistributionPlaceholder trades={trades} />
              <RegimeBreakdownPlaceholder />
            </div>

            <TradesSection
              trades={pagedTrades}
              total={sortedTrades.length}
              columns={tradeColumns}
              page={safePage}
              pageCount={pageCount}
              onPageChange={setPage}
              sortKey={sortKey}
              sortDir={sortDir}
              onSortChange={(k, d) => {
                setSortKey(k);
                setSortDir(d);
                setPage(0);
              }}
            />

            <AgentAttributionPlaceholder />
          </div>
        )}
      </div>
    </div>
  );
}

/* -------------------------------------------------------------------------- */

function HeadlineMetrics({
  roi,
  winRate,
  maxDrawdown,
  sharpe,
  profitFactor,
  avgReturn,
  totalTrades,
  winLoss,
}: {
  roi: number | null;
  winRate: number;
  maxDrawdown: number;
  sharpe: number;
  profitFactor: number;
  avgReturn: number;
  totalTrades: number;
  winLoss: { wins: number; losses: number; breakeven: number };
}) {
  return (
    <section className="rounded-md border border-border-subtle bg-bg-panel">
      <header className="flex items-center justify-between px-4 py-2.5 border-b border-border-subtle">
        <h2 className="text-[11px] font-semibold uppercase tracking-wider text-fg-muted">
          Headline
        </h2>
      </header>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-x-6 gap-y-4 px-4 py-4">
        <KeyValue
          layout="stacked"
          label="ROI"
          value={
            roi == null ? (
              <span className="text-fg-muted">—</span>
            ) : (
              <PnLBadge value={roi * 100} mode="pct" size="prominent" />
            )
          }
        />
        <KeyValue
          layout="stacked"
          label="Sharpe"
          value={Number.isFinite(sharpe) ? sharpe.toFixed(2) : "—"}
        />
        <KeyValue
          layout="stacked"
          label={
            <span className="inline-flex items-center gap-1.5">
              Sortino <Tag intent="warn">Pending</Tag>
            </span>
          }
          value={<span className="text-fg-muted">—</span>}
          hint="Backend doesn't return downside-deviation Sharpe yet."
        />
        <KeyValue
          layout="stacked"
          label="Max DD"
          value={
            <span className="text-ask-400 num-tabular">
              {(maxDrawdown * 100).toFixed(1)}%
            </span>
          }
        />
        <KeyValue
          layout="stacked"
          label="Trades"
          value={
            <span className="num-tabular">
              {totalTrades.toLocaleString()}
              <span className="text-fg-muted text-[12px] font-normal ml-2">
                {winLoss.wins}W · {winLoss.losses}L
                {winLoss.breakeven ? ` · ${winLoss.breakeven}B` : ""}
              </span>
            </span>
          }
        />
        <KeyValue
          layout="stacked"
          label="Win rate"
          value={`${(winRate * 100).toFixed(0)}%`}
        />
        <KeyValue
          layout="stacked"
          label={
            <span className="inline-flex items-center gap-1.5">
              avg R <Tag intent="warn">Pending</Tag>
            </span>
          }
          value={<span className="text-fg-muted">—</span>}
          hint="R-multiples need per-trade risk basis (not in result payload)."
        />
        <KeyValue
          layout="stacked"
          label="Profit factor"
          value={Number.isFinite(profitFactor) ? profitFactor.toFixed(2) : "—"}
          hint={`avg return ${(avgReturn * 100).toFixed(2)}%`}
        />
      </div>
    </section>
  );
}

function EquityCurveSection({
  equity,
  roi,
}: {
  equity: number[];
  roi: number | null;
}) {
  const hasData = equity.length >= 2;
  return (
    <section className="rounded-md border border-border-subtle bg-bg-panel">
      <header className="flex items-center justify-between gap-3 px-4 py-2.5 border-b border-border-subtle">
        <h2 className="text-[11px] font-semibold uppercase tracking-wider text-fg-muted">
          Equity curve
        </h2>
        <div className="flex items-center gap-2">
          <Tag intent="warn">Chart pending</Tag>
        </div>
      </header>
      <div className="px-4 py-5">
        {hasData ? (
          <div className="flex flex-col gap-3">
            <Sparkline
              values={equity}
              width={920}
              height={120}
              area
              tone={roi != null && roi >= 0 ? "bid" : "ask"}
              className="w-full h-[120px]"
            />
            <div className="flex items-center justify-between text-[11px] text-fg-muted num-tabular">
              <span>
                start{" "}
                <span className="text-fg-secondary">
                  {equity[0].toLocaleString(undefined, { maximumFractionDigits: 2 })}
                </span>
              </span>
              <span>
                {equity.length} samples
              </span>
              <span>
                end{" "}
                <span className="text-fg-secondary">
                  {equity[equity.length - 1].toLocaleString(undefined, { maximumFractionDigits: 2 })}
                </span>
              </span>
            </div>
            <p className="text-[11px] text-fg-muted leading-relaxed border-t border-border-subtle pt-3">
              Sparkline placeholder while the Chart primitive
              (<code className="font-mono text-[11px] text-fg-secondary">docs/design/04-component-specs/chart.md</code>)
              awaits implementation. Drawdown overlay, axis labels, crosshair
              tooltip, and per-tick timestamps unlock when Chart lands —
              the equity-curve usage is the canonical first integration.
            </p>
          </div>
        ) : (
          <p className="text-[12px] text-fg-muted">No equity samples in this run.</p>
        )}
      </div>
    </section>
  );
}

function DistributionPlaceholder({ trades }: { trades: SimulatedTrade[] }) {
  // Build a coarse pnl-percent histogram so the placeholder isn't fully empty.
  // R-multiple binning (the spec call) needs per-trade risk basis we don't
  // have, so this is pnl_pct distribution + Pending tag.
  const bins = useMemo(() => {
    if (trades.length === 0) return null;
    const longs = trades.filter((t) => t.direction === "BUY" && t.exit_price != null);
    const shorts = trades.filter((t) => t.direction === "SELL" && t.exit_price != null);
    const winsL = longs.filter((t) => t.pnl_pct > 0).length;
    const winsS = shorts.filter((t) => t.pnl_pct > 0).length;
    return {
      long: { total: longs.length, wins: winsL },
      short: { total: shorts.length, wins: winsS },
    };
  }, [trades]);

  return (
    <section className="rounded-md border border-border-subtle bg-bg-panel">
      <header className="flex items-center justify-between gap-3 px-4 py-2.5 border-b border-border-subtle">
        <h2 className="text-[11px] font-semibold uppercase tracking-wider text-fg-muted">
          Trade distribution
        </h2>
        <Tag intent="warn">Pending</Tag>
      </header>
      <div className="px-4 py-4 flex flex-col gap-3">
        {bins ? (
          <>
            <KeyValue
              label="Long trades"
              value={
                <span className="num-tabular">
                  {bins.long.total}
                  <span className="text-fg-muted text-[11px] ml-2">
                    {bins.long.total ? `${Math.round((bins.long.wins / bins.long.total) * 100)}% W` : ""}
                  </span>
                </span>
              }
            />
            <KeyValue
              label="Short trades"
              value={
                <span className="num-tabular">
                  {bins.short.total}
                  <span className="text-fg-muted text-[11px] ml-2">
                    {bins.short.total ? `${Math.round((bins.short.wins / bins.short.total) * 100)}% W` : ""}
                  </span>
                </span>
              }
            />
          </>
        ) : (
          <p className="text-[12px] text-fg-muted">No completed trades.</p>
        )}
        <p className="text-[11px] text-fg-muted leading-relaxed border-t border-border-subtle pt-3 flex items-start gap-2">
          <Info className="w-3.5 h-3.5 shrink-0 mt-0.5 text-warn-400" strokeWidth={1.5} aria-hidden />
          <span>
            Spec calls for an R-multiple histogram split long/short. Backend
            doesn&apos;t emit per-trade risk basis, so R-multiples can&apos;t
            be computed today. Histogram lands with the Chart primitive +
            backend additions to the result payload.
          </span>
        </p>
      </div>
    </section>
  );
}

function RegimeBreakdownPlaceholder() {
  return (
    <section className="rounded-md border border-border-subtle bg-bg-panel">
      <header className="flex items-center justify-between gap-3 px-4 py-2.5 border-b border-border-subtle">
        <h2 className="text-[11px] font-semibold uppercase tracking-wider text-fg-muted">
          Regime breakdown
        </h2>
        <Tag intent="warn">Pending</Tag>
      </header>
      <div className="px-4 py-4 flex flex-col gap-3 min-h-[140px] justify-center">
        <p className="text-[11px] text-fg-muted leading-relaxed flex items-start gap-2">
          <Info className="w-3.5 h-3.5 shrink-0 mt-0.5 text-warn-400" strokeWidth={1.5} aria-hidden />
          <span>
            Per-regime PnL (trending / range-bound / high-vol / crisis) needs
            the simulator to capture <code className="font-mono">regime_hmm</code>{" "}
            state on each trade and aggregate. Not in the result payload yet.
            Will render as a signed bar chart per Chart spec when both backend
            and Chart land.
          </span>
        </p>
      </div>
    </section>
  );
}

function TradesSection({
  trades,
  total,
  columns,
  page,
  pageCount,
  onPageChange,
  sortKey,
  sortDir,
  onSortChange,
}: {
  trades: SimulatedTrade[];
  total: number;
  columns: TableColumn<SimulatedTrade>[];
  page: number;
  pageCount: number;
  onPageChange: (n: number) => void;
  sortKey: string;
  sortDir: SortDirection;
  onSortChange: (k: string, d: SortDirection) => void;
}) {
  return (
    <section className="rounded-md border border-border-subtle bg-bg-panel">
      <header className="flex items-center justify-between gap-3 px-4 py-2.5 border-b border-border-subtle">
        <h2 className="text-[11px] font-semibold uppercase tracking-wider text-fg-muted">
          Trades
          <span className="ml-2 text-fg-secondary normal-case tracking-normal num-tabular">
            ({total.toLocaleString()})
          </span>
        </h2>
        <Tag intent="warn">Exit reason &amp; canvas-node link pending</Tag>
      </header>
      {total === 0 ? (
        <div className="px-4 py-8 text-center text-[12px] text-fg-muted">
          No trades in this run.
        </div>
      ) : (
        <>
          <div className="overflow-auto">
            <Table
              data={trades}
              columns={columns}
              rowKey={(t) => `${t.entry_time}-${t.direction}-${t.entry_price}`}
              density="standard"
              gridLines="horizontal"
              sortKey={sortKey}
              sortDirection={sortDir}
              onSortChange={onSortChange}
              emptyMessage="No trades on this page."
            />
          </div>
          {pageCount > 1 && (
            <footer className="flex items-center justify-between gap-3 px-4 py-2.5 border-t border-border-subtle">
              <p className="text-[11px] text-fg-muted num-tabular">
                Page <span className="text-fg-secondary">{page + 1}</span> /{" "}
                <span className="text-fg-secondary">{pageCount}</span>
                <span className="ml-2">
                  showing{" "}
                  {Math.min(total, page * TRADES_PAGE_SIZE + 1)}–
                  {Math.min(total, page * TRADES_PAGE_SIZE + trades.length)} of {total}
                </span>
              </p>
              <div className="flex items-center gap-1">
                <Button
                  intent="secondary"
                  size="sm"
                  leftIcon={<ChevronLeft className="w-3.5 h-3.5" />}
                  disabled={page === 0}
                  onClick={() => onPageChange(Math.max(0, page - 1))}
                >
                  Prev
                </Button>
                <Button
                  intent="secondary"
                  size="sm"
                  rightIcon={<ChevronRight className="w-3.5 h-3.5" />}
                  disabled={page >= pageCount - 1}
                  onClick={() => onPageChange(Math.min(pageCount - 1, page + 1))}
                >
                  Next
                </Button>
              </div>
            </footer>
          )}
        </>
      )}
    </section>
  );
}

function AgentAttributionPlaceholder() {
  // Per spec §2 (below-the-fold): per-agent attribution. Not in the result
  // payload — surface as Pending so the structure is visible and the gap
  // stays loud.
  return (
    <section className="rounded-md border border-border-subtle bg-bg-panel/60">
      <header className="flex items-center justify-between gap-3 px-4 py-2.5 border-b border-border-subtle">
        <h2 className="text-[11px] font-semibold uppercase tracking-wider text-fg-muted">
          Agent attribution
        </h2>
        <Tag intent="warn">Pending</Tag>
      </header>
      <div className="px-4 py-4">
        <p className="text-[11px] text-fg-muted leading-relaxed flex items-start gap-2">
          <Info className="w-3.5 h-3.5 shrink-0 mt-0.5 text-warn-400" strokeWidth={1.5} aria-hidden />
          <span>
            Spec §2 calls for per-agent score-vs-outcome correlation when the
            profile uses agents. Result payload doesn&apos;t persist agent
            scores per simulated trade — needs backend additions before the
            section can render. Live-trade attribution is available on the
            Trade Forensics surface (api.agentPerformance.attribution).
          </span>
        </p>
      </div>
    </section>
  );
}

function CanvasSnapshotButton({
  profileId,
  runId,
}: {
  profileId: string | null;
  runId: string;
}) {
  // Spec §2: "[view canvas as run]" opens the Pipeline Canvas in snapshot
  // mode — the canvas as it was when this run was archived. Per handoff
  // §2 the backend may not archive the canvas snapshot with the run yet;
  // surface as Pending until that lands.
  const disabled = !profileId;
  return (
    <span className="inline-flex items-center gap-2">
      <Tag intent="warn">Snapshot pending</Tag>
      <Button
        intent="secondary"
        size="md"
        leftIcon={<Workflow className="w-3.5 h-3.5" />}
        disabled={disabled}
        title={
          disabled
            ? "Run is not associated with a profile"
            : "Canvas snapshots are not archived with runs yet — opens current canvas, not the run-time version."
        }
        onClick={() => {
          if (!profileId) return;
          window.location.href = `/canvas/${encodeURIComponent(profileId)}?snapshot=${encodeURIComponent(runId)}`;
        }}
      >
        View canvas as run
      </Button>
    </span>
  );
}

function NotCompletedPanel({
  payload,
  onRetry,
}: {
  payload: BacktestPayload;
  onRetry: () => void;
}) {
  const status = payload.status;
  const isFailed = status === "failed";
  const detail = payload.error;
  return (
    <div className="mx-6 mt-6 rounded-md border border-border-subtle bg-bg-panel p-6 flex flex-col gap-3">
      <div className="flex items-center gap-3">
        {statusPill(status)}
        <h2 className="text-[15px] font-semibold text-fg">
          {isFailed ? "Run failed" : "Run is not yet complete"}
        </h2>
      </div>
      <p className="text-[13px] text-fg-secondary">
        {isFailed
          ? "The simulator returned an error. The diagnostic below is what the backend reported."
          : status === "running"
            ? "The simulator is still working. Multi-month 1m runs can take several minutes; check back, or follow live progress on the list page."
            : "This run is queued and hasn't started yet."}
      </p>
      {isFailed && detail && (
        <pre
          className={cn(
            "text-[12px] font-mono text-ask-300 whitespace-pre-wrap",
            "rounded-sm border border-ask-700/40 bg-ask-900/20 p-3"
          )}
        >
          {detail}
        </pre>
      )}
      <div className="flex items-center gap-2">
        <Button intent="secondary" size="md" onClick={onRetry}>
          Refresh
        </Button>
        <Link
          href="/backtests"
          className="inline-flex items-center gap-1 text-[13px] text-fg-secondary hover:text-fg transition-colors px-3 py-1.5"
        >
          <ArrowLeft className="w-3.5 h-3.5" strokeWidth={1.5} />
          Back to list
        </Link>
      </div>
    </div>
  );
}
