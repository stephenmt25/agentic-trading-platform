"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { Plus, Zap } from "lucide-react";

import { Pill, Sparkline, StatusDot } from "@/components/data-display";
import { Tag } from "@/components/primitives";
import { api, type ProfileResponse } from "@/lib/api/client";
import { useTradingModeStore, type TradingMode } from "@/lib/stores/tradingModeStore";
import { cn } from "@/lib/utils";

/**
 * /hot/profiles — comparison grid surface per ADR-018 + spec §9.1.
 * Sub-route of "Hot Trading" rail entry; COOL-mode observation view
 * (no order entry, no kill-switch interaction).
 *
 * Per-card data is aggregated client-side because the backend has no
 * per-profile `metricsSinceBoot` endpoint yet (tracked in TECH-DEBT):
 *
 *   - `api.profiles.list()`                    — active profiles + risk_limits
 *   - `api.agents.allRisk()`                   — per-profile drawdown/alloc/daily-pnl%
 *   - `api.audit.closedTrades(limit=500)`      — per-profile realized P&L + win rate
 *   - `api.positions.list({ status: 'open' })` — open-position counts grouped by profile
 *
 * Four total backend round-trips regardless of profile count. The N+1
 * shape was rejected (one call per profile × four endpoints) — see
 * TECH-DEBT row for the eventual per-profile aggregate endpoint.
 */

const POLL_INTERVAL_MS = 30_000;

interface CardData {
  profile_id: string;
  name: string;
  is_active: boolean;
  net_pnl_since_boot: number;
  trades_today: number;
  win_rate_today: number | null;
  drawdown_pct: number;
  allocation_pct: number;
  max_allocation_pct: number;
  open_positions: number;
  pnl_sparkline: number[];
  last_trade_at: string | null;
}

interface ClosedTrade {
  profile_id: string;
  realized_pnl: number;
  closed_at: string;
  outcome: string;
}

interface RiskRow {
  profile_id: string;
  daily_pnl_pct: number;
  drawdown_pct: number;
  allocation_pct: number;
}

interface OpenPosition {
  profile_id: string;
  status: string;
}

function isSameUtcDay(iso: string, now: Date): boolean {
  const t = Date.parse(iso);
  if (!Number.isFinite(t)) return false;
  const d = new Date(t);
  return (
    d.getUTCFullYear() === now.getUTCFullYear() &&
    d.getUTCMonth() === now.getUTCMonth() &&
    d.getUTCDate() === now.getUTCDate()
  );
}

function numFrom(rl: Record<string, unknown>, key: string, fallback: number): number {
  const v = rl[key];
  if (typeof v === "number" && Number.isFinite(v)) return v;
  if (typeof v === "string") {
    const p = parseFloat(v);
    if (Number.isFinite(p)) return p;
  }
  return fallback;
}

export default function HotProfilesPage() {
  const [cards, setCards] = useState<CardData[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const mode = useTradingModeStore((s) => s.mode);

  useEffect(() => {
    let cancelled = false;

    const load = async () => {
      try {
        const [profiles, risks, trades, positions] = await Promise.all([
          api.profiles.list(),
          api.agents.allRisk().catch(() => [] as RiskRow[]),
          api.audit
            .closedTrades({ limit: 500 })
            .catch(() => [] as ClosedTrade[]),
          api.positions
            .list({ status: "open" })
            .catch(() => [] as OpenPosition[]),
        ]);

        const active = profiles.filter((p) => p.is_active);
        const riskByProfile = new Map<string, RiskRow>(
          risks.map((r) => [r.profile_id, r])
        );

        // Group closed trades by profile_id. Already closed_at DESC from server.
        const tradesByProfile = new Map<string, ClosedTrade[]>();
        for (const t of trades) {
          if (!t.profile_id) continue;
          const arr = tradesByProfile.get(t.profile_id) ?? [];
          arr.push(t);
          tradesByProfile.set(t.profile_id, arr);
        }

        // Group open positions by profile_id.
        const openByProfile = new Map<string, number>();
        for (const p of positions) {
          if (p.status?.toLowerCase() !== "open") continue;
          openByProfile.set(
            p.profile_id,
            (openByProfile.get(p.profile_id) ?? 0) + 1
          );
        }

        const now = new Date();
        const rows: CardData[] = active.map((p: ProfileResponse) => {
          const ptrades = tradesByProfile.get(p.profile_id) ?? [];
          const todayTrades = ptrades.filter((t) =>
            isSameUtcDay(t.closed_at, now)
          );
          const wins = todayTrades.filter((t) => t.outcome === "win").length;
          const decided = todayTrades.filter(
            (t) => t.outcome === "win" || t.outcome === "loss"
          ).length;

          const netPnl = ptrades.reduce(
            (acc, t) => acc + (Number.isFinite(t.realized_pnl) ? t.realized_pnl : 0),
            0
          );

          // Sparkline: cumulative net P&L over the most recent 24 trades
          // (in chronological order). Server returned closed_at DESC.
          const last24 = ptrades.slice(0, 24).reverse();
          let running = 0;
          const sparkline = last24.map((t) => {
            running += Number.isFinite(t.realized_pnl) ? t.realized_pnl : 0;
            return running;
          });

          const rl = (p.risk_limits ?? {}) as Record<string, unknown>;
          const maxAlloc = numFrom(rl, "max_allocation_pct", 0.25);

          const risk = riskByProfile.get(p.profile_id);

          return {
            profile_id: p.profile_id,
            name: p.name,
            is_active: p.is_active,
            net_pnl_since_boot: netPnl,
            trades_today: todayTrades.length,
            win_rate_today: decided > 0 ? wins / decided : null,
            drawdown_pct: risk?.drawdown_pct ?? 0,
            allocation_pct: risk?.allocation_pct ?? 0,
            max_allocation_pct: maxAlloc,
            open_positions: openByProfile.get(p.profile_id) ?? 0,
            pnl_sparkline: sparkline,
            last_trade_at: ptrades[0]?.closed_at ?? null,
          };
        });

        // Sort: net P&L since boot DESC (spec §9.1).
        rows.sort((a, b) => b.net_pnl_since_boot - a.net_pnl_since_boot);

        if (!cancelled) {
          setCards(rows);
          setError(null);
          setLoading(false);
        }
      } catch (e) {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : "Failed to load profiles");
          setLoading(false);
        }
      }
    };

    load();
    const id = window.setInterval(load, POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, []);

  return (
    <div
      data-mode="cool"
      className="flex flex-col h-full bg-bg-canvas text-fg"
    >
      <header className="border-b border-border-subtle px-6 py-4">
        <div className="flex items-center gap-2 text-[12px] text-fg-muted">
          <Zap className="w-3.5 h-3.5" strokeWidth={1.5} aria-hidden />
          <span>Hot Trading / Profiles</span>
        </div>
        <h1 className="text-[18px] font-semibold tracking-tight text-fg mt-1.5">
          Profile comparison
        </h1>
        <p className="text-[12px] text-fg-muted mt-0.5">
          One card per active profile, sorted by net P&L since boot. Engine
          totals are in chrome.
        </p>
      </header>

      <div className="flex-1 min-h-0 overflow-auto px-6 py-6">
        {error ? (
          <ErrorState message={error} />
        ) : loading && !cards ? (
          <LoadingState />
        ) : cards && cards.length === 0 ? (
          <EmptyState />
        ) : (
          <>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {cards?.map((card) => (
                <ProfileCard key={card.profile_id} card={card} mode={mode} />
              ))}
              <AddProfileCard />
            </div>
          </>
        )}
      </div>
    </div>
  );
}

function ProfileCard({
  card,
  mode,
}: {
  card: CardData;
  mode: TradingMode | null;
}) {
  const pnlPositive = card.net_pnl_since_boot >= 0;
  const pnlClass = pnlPositive ? "text-bid-300" : "text-danger-500";

  const allocRatio =
    card.max_allocation_pct > 0
      ? card.allocation_pct / card.max_allocation_pct
      : 0;
  const allocWarn = allocRatio >= 0.85;

  const ddPct = card.drawdown_pct;
  const ddDanger = ddPct >= 0.05;
  const ddWarn = !ddDanger && ddPct >= 0.025;

  return (
    <article
      className={cn(
        "rounded-md border bg-bg-panel p-4 flex flex-col gap-3 group",
        "transition-colors hover:border-border-strong"
      )}
    >
      <header className="flex items-start justify-between gap-2">
        <Link
          href={`/hot/profiles/${encodeURIComponent(card.profile_id)}`}
          className="flex-1 min-w-0"
        >
          <h2
            className="text-[14px] font-medium text-fg truncate group-hover:text-accent-300"
            title={card.name}
          >
            {card.name}
          </h2>
          <p className="text-[10px] font-mono text-fg-muted truncate mt-0.5">
            {card.profile_id.slice(0, 12)}…
          </p>
        </Link>
        <div className="flex items-center gap-1.5 shrink-0">
          <StatusDot
            state={card.is_active ? "live" : "idle"}
            size={6}
            pulse={card.is_active}
            aria-label={card.is_active ? "Active" : "Idle"}
          />
          {mode && (
            <Pill intent={mode === "LIVE" ? "danger" : "warn"}>
              {mode.toLowerCase()}
            </Pill>
          )}
        </div>
      </header>

      <Link
        href={`/hot/profiles/${encodeURIComponent(card.profile_id)}?tab=daily-pnl`}
        className="flex items-end justify-between gap-3 rounded-sm -m-1 p-1 hover:bg-bg-raised"
      >
        <div>
          <p className="text-[10px] uppercase tracking-wider text-fg-muted num-tabular">
            Net P&L since boot
          </p>
          <p
            className={cn(
              "text-[20px] font-semibold tracking-tight num-tabular leading-none mt-1",
              pnlClass
            )}
          >
            {pnlPositive ? "+" : ""}
            {card.net_pnl_since_boot.toLocaleString(undefined, {
              minimumFractionDigits: 2,
              maximumFractionDigits: 2,
            })}
          </p>
        </div>
        <Sparkline
          values={card.pnl_sparkline}
          width={120}
          height={32}
          area
          tone={pnlPositive ? "bid" : "ask"}
        />
      </Link>

      <dl className="grid grid-cols-2 gap-x-3 gap-y-1.5 text-[12px] num-tabular pt-1 border-t border-border-subtle">
        <Row
          label="Trades today"
          value={card.trades_today.toLocaleString()}
        />
        <Row
          label="Win rate"
          value={
            card.win_rate_today === null
              ? "—"
              : `${(card.win_rate_today * 100).toFixed(1)}%`
          }
        />
        <Row
          label="Drawdown"
          value={
            <Link
              href="/risk"
              className={cn(
                "hover:underline",
                ddDanger
                  ? "text-danger-500"
                  : ddWarn
                    ? "text-warn-400"
                    : "text-fg"
              )}
            >
              {ddPct === 0 ? "0.00%" : `-${(ddPct * 100).toFixed(2)}%`}
            </Link>
          }
        />
        <Row
          label="Alloc / cap"
          value={
            <span
              className={cn(
                allocWarn ? "text-warn-400" : "text-fg",
                "num-tabular"
              )}
            >
              {(card.allocation_pct * 100).toFixed(1)}% /{" "}
              <span className="text-fg-muted">
                {(card.max_allocation_pct * 100).toFixed(0)}%
              </span>
            </span>
          }
        />
      </dl>

      <footer className="flex items-center justify-between text-[11px] text-fg-muted pt-2 border-t border-border-subtle">
        <span>
          {card.open_positions > 0 ? (
            <Link
              href={`/hot/profiles/${encodeURIComponent(card.profile_id)}?tab=positions`}
              className="text-accent-300 hover:text-accent-200 num-tabular"
            >
              {card.open_positions} open position
              {card.open_positions === 1 ? "" : "s"}
            </Link>
          ) : (
            <span>no open positions</span>
          )}
        </span>
        <span className="num-tabular">
          {card.last_trade_at
            ? `last trade ${formatRelative(card.last_trade_at)}`
            : "no trades yet"}
        </span>
      </footer>
    </article>
  );
}

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <>
      <dt className="text-fg-muted">{label}</dt>
      <dd className="text-right">{value}</dd>
    </>
  );
}

function AddProfileCard() {
  return (
    <Link
      href="/canvas"
      className={cn(
        "rounded-md border border-dashed border-border-subtle bg-bg-panel/40",
        "flex flex-col items-center justify-center gap-2 p-6 min-h-[200px]",
        "text-fg-muted hover:text-fg hover:border-accent-500/50 transition-colors"
      )}
    >
      <Plus className="w-5 h-5" strokeWidth={1.5} aria-hidden />
      <span className="text-[12px]">Add profile</span>
      <span className="text-[10px] text-fg-muted text-center">
        Open Pipeline Canvas to create or activate one
      </span>
    </Link>
  );
}

function EmptyState() {
  return (
    <div className="max-w-md mx-auto mt-12 text-center flex flex-col items-center gap-3">
      <div className="w-12 h-12 rounded-full bg-bg-panel border border-border-subtle flex items-center justify-center">
        <Zap className="w-5 h-5 text-fg-muted" strokeWidth={1.5} aria-hidden />
      </div>
      <p className="text-[14px] text-fg">No active profiles</p>
      <p className="text-[12px] text-fg-muted">
        Activate one in{" "}
        <Link
          href="/canvas"
          className="text-accent-300 hover:text-accent-200 underline"
        >
          Pipeline Canvas
        </Link>{" "}
        to begin observation.
      </p>
    </div>
  );
}

function LoadingState() {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      {[0, 1, 2].map((i) => (
        <div
          key={i}
          className="rounded-md border border-border-subtle bg-bg-panel p-4 min-h-[200px] animate-pulse"
        >
          <div className="h-3 w-32 rounded bg-bg-raised mb-3" />
          <div className="h-6 w-24 rounded bg-bg-raised mb-4" />
          <div className="h-2 w-full rounded bg-bg-raised" />
        </div>
      ))}
    </div>
  );
}

function ErrorState({ message }: { message: string }) {
  return (
    <div className="rounded-md border border-danger-700/40 bg-danger-700/10 p-4 text-[12px] text-danger-500">
      <p className="font-medium mb-1">Couldn&rsquo;t load profiles</p>
      <p className="text-fg-muted">{message}</p>
      <p className="mt-2">
        <Tag intent="warn">retry on next 30s poll</Tag>
      </p>
    </div>
  );
}

function formatRelative(iso: string): string {
  const t = Date.parse(iso);
  if (!Number.isFinite(t)) return iso;
  const diff = Date.now() - t;
  if (diff < 60_000) return `${Math.floor(diff / 1000)}s ago`;
  if (diff < 3_600_000) return `${Math.floor(diff / 60_000)}m ago`;
  if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)}h ago`;
  return `${Math.floor(diff / 86_400_000)}d ago`;
}
