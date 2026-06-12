"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { ChevronRight, RefreshCw } from "lucide-react";
import { api, type PaperTradingStatus } from "@/lib/api/client";
import { usePaperTradingStatus } from "@/lib/api/hooks";
import { Sparkline, Pill } from "@/components/data-display";
import { Tag } from "@/components/primitives";
import { cn } from "@/lib/utils";
import { DetailDrawer } from "./DetailDrawer";

interface DailyPnlTabProps {
  profileId: string;
  selectedDate: string | null;
  onSelect: (date: string | null) => void;
}

type DailyReport = PaperTradingStatus["daily_reports"][number];

export function DailyPnlTab({
  profileId,
  selectedDate,
  onSelect,
}: DailyPnlTabProps) {
  // FE-W2.1: shared ["paperTradingStatus"] query (same payload the chrome
  // EngineTotalsPill reads — one network request serves both). The hook's
  // 30s interval supersedes this tab's old 60s setInterval.
  const statusQuery = usePaperTradingStatus();
  const status = statusQuery.data ?? null;
  const loading = statusQuery.isPending;
  const refreshing = statusQuery.isFetching;
  const error = statusQuery.error
    ? statusQuery.error instanceof Error
      ? statusQuery.error.message
      : "Failed to load daily reports"
    : null;
  const load = () => statusQuery.refetch();

  const reports = useMemo(() => {
    if (!status) return [];
    // status returns most-recent first; we want chronological for the sparkline.
    return [...status.daily_reports];
  }, [status]);

  const sparklineValues = useMemo(() => {
    // chronological asc for left-to-right reading
    const asc = [...reports].reverse();
    return asc.map((r) => r.net_pnl);
  }, [reports]);

  const totalNet = useMemo(
    () => reports.reduce((acc, r) => acc + (r.net_pnl ?? 0), 0),
    [reports]
  );

  return (
    <div className="flex flex-col h-full min-h-0">
      <div className="shrink-0 px-4 py-3 border-b border-border-subtle flex flex-col gap-3">
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-[10px] uppercase tracking-wider text-fg-muted">
              Engine net P&L · last {reports.length} day
              {reports.length === 1 ? "" : "s"}
            </p>
            <p
              className={cn(
                "text-[18px] font-semibold tracking-tight num-tabular leading-none mt-1",
                totalNet >= 0 ? "text-bid-300" : "text-danger-500"
              )}
            >
              {totalNet >= 0 ? "+" : ""}
              {totalNet.toLocaleString(undefined, {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2,
              })}
            </p>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <Tag intent="warn">engine-wide</Tag>
            <button
              type="button"
              onClick={load}
              aria-label="Refresh"
              className="h-7 w-7 rounded-md flex items-center justify-center text-fg-muted hover:text-fg hover:bg-bg-raised"
            >
              <RefreshCw
                className={cn(
                  "w-3 h-3",
                  refreshing && "animate-spin will-change-transform"
                )}
                strokeWidth={1.5}
                aria-hidden
              />
            </button>
          </div>
        </div>
        <div className="rounded-md border border-border-subtle bg-bg-panel/60 px-3 py-2.5">
          <Sparkline
            values={sparklineValues}
            width={600}
            height={48}
            area
            withMid
            className="w-full h-12"
          />
        </div>
        <p className="text-[11px] text-fg-muted">
          Daily reports are engine-wide totals — the day drawer below filters
          trade lineage to this profile. Per-profile daily summaries need a
          backend aggregator (TECH-DEBT).
        </p>
      </div>

      <div className="flex-1 min-h-0 overflow-auto">
        {error ? (
          <ErrorBlock message={error} />
        ) : !loading && reports.length === 0 ? (
          <EmptyBlock />
        ) : (
          <table className="w-full text-[12px] num-tabular border-separate border-spacing-0">
            <thead className="sticky top-0 z-10 bg-bg-canvas">
              <tr>
                <Th align="left">Date</Th>
                <Th align="right">Trades</Th>
                <Th align="right">Win rate</Th>
                <Th align="right">Gross</Th>
                <Th align="right">Net</Th>
                <Th align="right">Max DD</Th>
                <Th align="right">Sharpe</Th>
                <Th align="right" />
              </tr>
            </thead>
            <tbody>
              {reports.map((r) => (
                <DayRow
                  key={r.id}
                  report={r}
                  selected={selectedDate === r.report_date}
                  onSelect={() =>
                    onSelect(
                      selectedDate === r.report_date ? null : r.report_date
                    )
                  }
                />
              ))}
            </tbody>
          </table>
        )}
      </div>

      <DetailDrawer
        open={!!selectedDate}
        onClose={() => onSelect(null)}
        kind="daily-report"
        title={selectedDate ? selectedDate : "Daily report"}
        subtitle={
          selectedDate ? (
            <span>full transparency · this profile</span>
          ) : undefined
        }
      >
        {selectedDate && (
          <DailyReportDrawer date={selectedDate} profileId={profileId} />
        )}
      </DetailDrawer>
    </div>
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
        "px-3 h-8 text-[10px] uppercase tracking-wider font-medium text-fg-muted",
        "bg-bg-canvas border-b border-border-subtle",
        align === "right" ? "text-right" : "text-left"
      )}
    >
      {children}
    </th>
  );
}

function DayRow({
  report,
  selected,
  onSelect,
}: {
  report: DailyReport;
  selected: boolean;
  onSelect: () => void;
}) {
  const positive = report.net_pnl >= 0;
  return (
    <tr
      onClick={onSelect}
      className={cn(
        "cursor-pointer group",
        selected
          ? "bg-accent-500/10"
          : "bg-transparent hover:bg-bg-rowhover"
      )}
      aria-selected={selected}
    >
      <Td>
        <span
          aria-hidden
          className={cn(
            "absolute left-0 top-0 bottom-0 w-0.5",
            positive ? "bg-bid-500/60" : "bg-danger-500/60",
            selected && "bg-accent-500"
          )}
        />
        <span className="font-mono text-fg">{report.report_date}</span>
      </Td>
      <Td align="right">
        <span className="font-mono text-fg-secondary">
          {report.total_trades}
        </span>
      </Td>
      <Td align="right">
        <span className="font-mono text-fg-secondary">
          {(report.win_rate * 100).toFixed(1)}%
        </span>
      </Td>
      <Td align="right">
        <span className="font-mono text-fg-secondary">
          {fmtSigned(report.gross_pnl)}
        </span>
      </Td>
      <Td align="right">
        <span
          className={cn(
            "font-mono font-medium",
            positive ? "text-bid-300" : "text-danger-500"
          )}
        >
          {fmtSigned(report.net_pnl)}
        </span>
      </Td>
      <Td align="right">
        <span className="font-mono text-warn-400">
          {report.max_drawdown
            ? `-${(report.max_drawdown * 100).toFixed(2)}%`
            : "—"}
        </span>
      </Td>
      <Td align="right">
        <span className="font-mono text-fg-secondary">
          {report.sharpe_ratio.toFixed(2)}
        </span>
      </Td>
      <Td align="right">
        <ChevronRight
          className={cn(
            "w-3.5 h-3.5 transition-opacity ml-auto",
            selected
              ? "text-accent-300 opacity-100"
              : "text-fg-muted opacity-0 group-hover:opacity-100"
          )}
          strokeWidth={1.5}
          aria-hidden
        />
      </Td>
    </tr>
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
        "relative px-3 h-8 border-b border-border-subtle/60",
        align === "right" ? "text-right" : "text-left"
      )}
    >
      {children}
    </td>
  );
}

interface DrawerProps {
  date: string;
  profileId: string;
}

type Detail = Awaited<ReturnType<typeof api.paperTrading.reportDetail>>;

function DailyReportDrawer({ date, profileId }: DrawerProps) {
  const [detail, setDetail] = useState<Detail | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setErr(null);
    api.paperTrading
      .reportDetail(date)
      .then((d) => {
        if (!cancelled) setDetail(d);
      })
      .catch((e: unknown) => {
        if (!cancelled)
          setErr(e instanceof Error ? e.message : "lookup failed");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [date]);

  const trades = useMemo(() => {
    if (!detail) return [];
    return detail.trades.filter((t) => t.decision_profile_id === profileId);
  }, [detail, profileId]);

  const blocked = useMemo(() => {
    if (!detail) return [];
    return detail.blocked.recent.filter((b) => b.profile_id === profileId);
  }, [detail, profileId]);

  const profileSummary = useMemo(() => {
    if (trades.length === 0) return null;
    let gross = 0;
    let wins = 0;
    let decided = 0;
    for (const t of trades) {
      gross += t.realized_pnl;
      if (t.outcome === "win") wins++;
      if (t.outcome === "win" || t.outcome === "loss") decided++;
    }
    return {
      total_trades: trades.length,
      net_pnl: gross,
      win_rate: decided > 0 ? wins / decided : null,
    };
  }, [trades]);

  if (loading) {
    return (
      <div className="px-4 py-6 text-[12px] text-fg-muted">
        Loading report for {date}…
      </div>
    );
  }
  if (err) {
    return (
      <div className="m-4 rounded-md border border-danger-700/40 bg-danger-700/10 p-3 text-[12px] text-danger-500">
        Couldn&rsquo;t load report: {err}
      </div>
    );
  }
  if (!detail) return null;

  return (
    <div className="px-4 py-3 flex flex-col gap-4 text-[12px]">
      <Section label="Engine totals (this day)">
        <KV
          label="Trades"
          value={detail.summary?.total_trades.toLocaleString() ?? "—"}
        />
        <KV
          label="Win rate"
          value={
            detail.summary
              ? `${(detail.summary.win_rate * 100).toFixed(1)}%`
              : "—"
          }
        />
        <KV
          label="Net P&L"
          value={
            <span
              className={
                detail.summary && detail.summary.net_pnl >= 0
                  ? "text-bid-300"
                  : "text-danger-500"
              }
            >
              {detail.summary ? fmtSigned(detail.summary.net_pnl) : "—"}
            </span>
          }
        />
        <KV
          label="Sharpe"
          value={detail.summary?.sharpe_ratio.toFixed(2) ?? "—"}
        />
      </Section>

      <Section label="This profile (filtered)">
        {profileSummary ? (
          <>
            <KV
              label="Trades"
              value={profileSummary.total_trades.toString()}
            />
            <KV
              label="Win rate"
              value={
                profileSummary.win_rate === null
                  ? "—"
                  : `${(profileSummary.win_rate * 100).toFixed(1)}%`
              }
            />
            <KV
              label="Net P&L"
              value={
                <span
                  className={
                    profileSummary.net_pnl >= 0
                      ? "text-bid-300"
                      : "text-danger-500"
                  }
                >
                  {fmtSigned(profileSummary.net_pnl)}
                </span>
              }
            />
            <KV
              label="Blocked"
              value={blocked.length.toString()}
            />
          </>
        ) : (
          <p className="col-span-2 text-fg-muted">
            No closed trades for this profile on {date}.
          </p>
        )}
      </Section>

      {trades.length > 0 && (
        <section className="flex flex-col gap-1.5">
          <h3 className="text-[10px] uppercase tracking-wider text-fg-muted">
            Closed trades ({trades.length})
          </h3>
          <ul className="flex flex-col gap-1.5">
            {trades.map((t) => (
              <TradeCard key={t.position_id} trade={t} />
            ))}
          </ul>
        </section>
      )}

      {blocked.length > 0 && (
        <section className="flex flex-col gap-1.5">
          <h3 className="text-[10px] uppercase tracking-wider text-fg-muted">
            Blocked attempts ({blocked.length})
          </h3>
          <ul className="flex flex-col gap-1.5">
            {blocked.slice(0, 10).map((b) => (
              <BlockedCard key={b.event_id} blocked={b} />
            ))}
          </ul>
          {blocked.length > 10 && (
            <p className="text-[11px] text-fg-muted">
              Showing 10 of {blocked.length} blocked attempts.
            </p>
          )}
        </section>
      )}
    </div>
  );
}

function TradeCard({ trade }: { trade: Detail["trades"][number] }) {
  const positive = trade.realized_pnl >= 0;
  return (
    <li className="rounded-md border border-border-subtle bg-bg-canvas px-3 py-2 flex flex-col gap-1.5">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className="font-mono text-fg text-[12px]">{trade.symbol}</span>
          <Pill
            intent={
              positive ? "bid" : trade.outcome === "loss" ? "danger" : "neutral"
            }
          >
            {trade.outcome}
          </Pill>
        </div>
        <span
          className={cn(
            "text-[12px] font-mono font-medium num-tabular",
            positive ? "text-bid-300" : "text-danger-500"
          )}
        >
          {fmtSigned(trade.realized_pnl)}{" "}
          <span className="text-fg-muted">
            ({(trade.realized_pnl_pct * 100).toFixed(2)}%)
          </span>
        </span>
      </div>
      <dl className="grid grid-cols-2 gap-x-3 gap-y-0.5 text-[11px] num-tabular">
        <KV
          label="Entry → Exit"
          value={
            <span className="font-mono">
              ${trade.entry_price.toFixed(2)} → ${trade.exit_price.toFixed(2)}
            </span>
          }
        />
        <KV
          label="Held"
          value={fmtDuration(trade.holding_duration_s)}
        />
        <KV
          label="Reason"
          value={
            <span className="font-mono text-fg-muted">
              {trade.close_reason || "—"}
            </span>
          }
        />
        {trade.order && (
          <KV
            label="Slip"
            value={
              trade.order.slippage_pct !== null
                ? `${(trade.order.slippage_pct * 100).toFixed(3)}%`
                : "—"
            }
          />
        )}
      </dl>
      {trade.decision_event_id && (
        <Link
          href={`/hot/profiles/${encodeURIComponent(trade.decision_profile_id ?? "")}?tab=decisions&decision=${encodeURIComponent(trade.decision_event_id)}`}
          className="text-[11px] text-accent-300 hover:text-accent-200 self-start mt-0.5"
        >
          view decision lineage →
        </Link>
      )}
    </li>
  );
}

function BlockedCard({
  blocked,
}: {
  blocked: Detail["blocked"]["recent"][number];
}) {
  const reasons = blocked.gates
    ? Object.entries(blocked.gates)
        .filter(([, g]) => g.passed === false)
        .map(([name, g]) => `${name}${g.reason ? ` (${g.reason})` : ""}`)
        .slice(0, 3)
    : [];

  return (
    <li className="rounded-md border border-border-subtle bg-bg-canvas px-3 py-2 flex items-start justify-between gap-3">
      <div className="min-w-0 flex-1">
        <p className="font-mono text-[12px] text-fg-secondary truncate">
          {blocked.symbol} · {blocked.outcome}
        </p>
        {reasons.length > 0 && (
          <p className="text-[11px] text-danger-500 mt-0.5 truncate">
            {reasons.join(" · ")}
          </p>
        )}
      </div>
      <span className="text-[11px] text-fg-muted shrink-0 num-tabular">
        {fmtTime(blocked.created_at)}
      </span>
    </li>
  );
}

function Section({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <section className="flex flex-col gap-1.5">
      <h3 className="text-[10px] uppercase tracking-wider text-fg-muted">
        {label}
      </h3>
      <dl className="grid grid-cols-2 gap-x-3 gap-y-1 rounded-md border border-border-subtle bg-bg-canvas px-3 py-2">
        {children}
      </dl>
    </section>
  );
}

function KV({
  label,
  value,
}: {
  label: string;
  value: React.ReactNode;
}) {
  return (
    <>
      <dt className="text-fg-muted">{label}</dt>
      <dd className="text-right text-fg num-tabular">{value}</dd>
    </>
  );
}

function ErrorBlock({ message }: { message: string }) {
  return (
    <div className="m-4 rounded-md border border-danger-700/40 bg-danger-700/10 p-3 text-[12px] text-danger-500">
      <p className="font-medium">Couldn&rsquo;t load daily reports</p>
      <p className="text-fg-muted mt-0.5">{message}</p>
    </div>
  );
}

function EmptyBlock() {
  return (
    <div className="m-4 rounded-md border border-border-subtle bg-bg-panel p-4 text-[12px] text-fg-muted text-center">
      No completed trading days yet. Reports generate at 00:00 UTC.
    </div>
  );
}

function fmtSigned(n: number): string {
  const sign = n > 0 ? "+" : "";
  return `${sign}${n.toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

function fmtTime(iso: string | null): string {
  if (!iso) return "—";
  const t = Date.parse(iso);
  if (!Number.isFinite(t)) return "—";
  return new Date(t).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
  });
}

function fmtDuration(seconds: number): string {
  if (seconds < 60) return `${seconds}s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m`;
  if (seconds < 86400) return `${(seconds / 3600).toFixed(1)}h`;
  return `${(seconds / 86400).toFixed(1)}d`;
}
