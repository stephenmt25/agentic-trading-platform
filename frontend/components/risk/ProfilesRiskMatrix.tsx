"use client";

import { useMemo } from "react";
import Link from "next/link";
import {
  AlertTriangle,
  BarChart3,
  ChevronRight,
  ShieldAlert,
  TrendingDown,
  Wallet,
} from "lucide-react";

import { useAllRisk, usePositions, useProfiles } from "@/lib/api/hooks";

/**
 * ProfilesRiskMatrix — horizontally-scrollable grid of per-profile risk
 * cards rendered above the kill switch on /risk. Spec:
 * docs/design/05-surface-specs/05-risk-control.md §1.1.
 *
 * Phase 10.1 lift-and-shift per ADR-018: the per-profile RiskBar visual
 * is inlined from frontend/components/risk/RiskMonitorCard.tsx so each
 * card can be its own click target (legacy component renders divs, not
 * links). Token-contract rewrite to the redesign surface is Phase 10.5.
 *
 * Sorted by drawdown severity (worst first) per spec — the operator's
 * stress-moment question is "which profile needs intervening on first?".
 */

// FE-W2: the old setInterval cycle made 1 + 2N requests per pass (profiles
// + per-profile risk + per-profile positions). It now collapses onto THREE
// shared React Query reads: useProfiles + useAllRisk (one /agents/risk —
// same per-row shape as /agents/risk/{id}) + ONE usePositions fetch grouped
// client-side by profile_id. 30s cadence kept (see git history for the
// 6-per-origin browser-cap rationale); refetching stops on unmount and
// pauses while the tab is hidden.
const POLL_INTERVAL_MS = 30_000;
const DEFAULT_DD_THRESHOLD = 0.1;

interface MatrixRow {
  profile_id: string;
  name: string;
  daily_pnl_pct: number;
  drawdown_pct: number;
  allocation_pct: number;
  max_allocation_pct: number;
  auto_pause_drawdown_pct: number;
  open_count: number;
  exposure_usdc: number;
}

function numOr<T extends number>(v: unknown, fallback: T): number {
  if (typeof v === "number" && Number.isFinite(v)) return v;
  if (typeof v === "string") {
    const parsed = parseFloat(v);
    if (Number.isFinite(parsed)) return parsed;
  }
  return fallback;
}

export function ProfilesRiskMatrix() {
  // Three shared queries replace the 1 + 2N request cycle. The profiles
  // read is the shared ["profiles"] cache (on-demand, no extra interval);
  // allRisk + positions poll at 30s. Per-resource failures degrade exactly
  // like the old per-profile .catch fallbacks: missing risk → zeros,
  // missing positions → empty (last good data is kept on refetch errors).
  const profilesQuery = useProfiles();
  const allRiskQuery = useAllRisk({ refetchInterval: POLL_INTERVAL_MS });
  const positionsQuery = usePositions(undefined, {
    status: "open",
    refetchInterval: POLL_INTERVAL_MS,
  });

  const loading = profilesQuery.isPending;
  const error = profilesQuery.isError
    ? profilesQuery.error instanceof Error
      ? profilesQuery.error.message
      : "Failed to load matrix"
    : null;

  const rows = useMemo<MatrixRow[]>(() => {
    const active = (profilesQuery.data ?? []).filter((p) => p.is_active);
    if (active.length === 0) return [];

    const riskById = new Map(
      (allRiskQuery.data ?? []).map((r) => [r.profile_id, r])
    );

    // ONE positions fetch, grouped client-side by profile_id.
    const openByProfile = new Map<
      string,
      { count: number; exposure: number }
    >();
    for (const pos of positionsQuery.data ?? []) {
      if (pos.status?.toLowerCase() !== "open") continue;
      const acc = openByProfile.get(pos.profile_id) ?? {
        count: 0,
        exposure: 0,
      };
      acc.count += 1;
      const n = parseFloat(pos.notional ?? "0");
      if (Number.isFinite(n)) acc.exposure += Math.abs(n);
      openByProfile.set(pos.profile_id, acc);
    }

    return active
      .map((p) => {
        const risk = riskById.get(p.profile_id);
        const open = openByProfile.get(p.profile_id);

        const rl = (p.risk_limits ?? {}) as Record<string, unknown>;
        const maxAlloc = numOr(rl["max_allocation_pct"], 0.25);
        const autoPause = numOr(
          rl["auto_pause_drawdown_pct"] ?? rl["max_drawdown_pct"],
          DEFAULT_DD_THRESHOLD
        );

        const row: MatrixRow = {
          profile_id: p.profile_id,
          name: p.name,
          daily_pnl_pct: risk?.daily_pnl_pct ?? 0,
          drawdown_pct: risk?.drawdown_pct ?? 0,
          allocation_pct: risk?.allocation_pct ?? 0,
          max_allocation_pct: maxAlloc,
          auto_pause_drawdown_pct: autoPause,
          open_count: open?.count ?? 0,
          exposure_usdc: open?.exposure ?? 0,
        };
        return row;
      })
      // Sort: worst drawdown first (largest drawdown_pct).
      .sort((a, b) => b.drawdown_pct - a.drawdown_pct);
  }, [profilesQuery.data, allRiskQuery.data, positionsQuery.data]);

  const headerCount = rows.length;

  return (
    <section className="flex flex-col gap-2">
      <header className="flex items-center justify-between">
        <h2 className="text-[10px] uppercase tracking-wider text-fg-muted num-tabular">
          Profiles risk matrix
        </h2>
        <span className="text-[11px] text-fg-muted num-tabular">
          {headerCount > 0
            ? `${headerCount} active profile${headerCount === 1 ? "" : "s"} · worst drawdown first`
            : ""}
        </span>
      </header>

      {error ? (
        <div className="rounded-md border border-danger-700/40 bg-danger-700/10 p-4 flex items-center gap-2 text-[12px] text-danger-500">
          <ShieldAlert className="w-4 h-4" strokeWidth={1.5} aria-hidden />
          <span>Risk API unavailable — {error}</span>
        </div>
      ) : loading && rows.length === 0 ? (
        <div className="rounded-md border border-border-subtle bg-bg-panel p-4 text-[12px] text-fg-muted">
          Loading active profiles…
        </div>
      ) : rows.length === 0 ? (
        <div className="rounded-md border border-border-subtle bg-bg-panel p-4 text-[12px] text-fg-muted">
          No active profiles. Risk Control monitors active trading; activate a
          profile in{" "}
          <Link
            href="/canvas"
            className="text-accent-300 hover:text-accent-200 underline"
          >
            Pipeline Canvas
          </Link>{" "}
          to populate this matrix.
        </div>
      ) : (
        <div
          className="flex gap-3 overflow-x-auto pb-2 -mx-1 px-1 snap-x snap-mandatory"
          role="list"
        >
          {rows.map((row) => (
            <MatrixCard key={row.profile_id} row={row} />
          ))}
        </div>
      )}
    </section>
  );
}

function MatrixCard({ row }: { row: MatrixRow }) {
  const ddRatio =
    row.auto_pause_drawdown_pct > 0
      ? row.drawdown_pct / row.auto_pause_drawdown_pct
      : 0;
  const ddDanger = ddRatio >= 0.85;
  const ddWarn = !ddDanger && ddRatio >= 0.5;

  const allocRatio =
    row.max_allocation_pct > 0
      ? row.allocation_pct / row.max_allocation_pct
      : 0;
  const allocDanger = allocRatio >= 1;
  const allocWarn = !allocDanger && allocRatio >= 0.75;

  return (
    <article
      role="listitem"
      className={`shrink-0 w-72 snap-start rounded-md border bg-bg-panel p-3 flex flex-col gap-3 ${
        ddDanger
          ? "border-danger-700/50"
          : ddWarn
            ? "border-warn-700/50"
            : "border-border-subtle"
      }`}
    >
      <div className="flex items-start justify-between gap-2">
        <Link
          href={`/hot/profiles/${encodeURIComponent(row.profile_id)}`}
          className="min-w-0 flex-1 group"
        >
          <p
            className="text-[13px] font-medium text-fg truncate group-hover:text-accent-300"
            title={row.name}
          >
            {row.name}
          </p>
          <p className="text-[10px] text-fg-muted font-mono truncate">
            {row.profile_id.slice(0, 12)}…
          </p>
        </Link>
        {ddDanger && (
          <span className="text-[10px] font-medium text-danger-500 border border-danger-700/40 rounded-sm px-1.5 py-0.5 num-tabular">
            CB
          </span>
        )}
      </div>

      <Link
        href={`/hot/profiles/${encodeURIComponent(row.profile_id)}?tab=daily-pnl`}
        className="block rounded-sm -m-1 p-1 hover:bg-bg-raised"
      >
        <RiskBar
          label="Drawdown"
          icon={<TrendingDown className="w-3 h-3" strokeWidth={1.5} />}
          currentLabel={`${(row.drawdown_pct * 100).toFixed(2)}%`}
          limitLabel={`${(row.auto_pause_drawdown_pct * 100).toFixed(0)}% cap`}
          pct={Math.min(100, Math.max(0, ddRatio * 100))}
          danger={ddDanger}
          warn={ddWarn}
        />
      </Link>

      <RiskBar
        label="Allocation"
        icon={<BarChart3 className="w-3 h-3" strokeWidth={1.5} />}
        currentLabel={`${(row.allocation_pct * 100).toFixed(1)}%`}
        limitLabel={`${(row.max_allocation_pct * 100).toFixed(0)}% max`}
        pct={Math.min(100, Math.max(0, allocRatio * 100))}
        danger={allocDanger}
        warn={allocWarn}
      />

      <dl className="grid grid-cols-2 gap-x-3 gap-y-1.5 text-[11px] num-tabular pt-1 border-t border-border-subtle">
        <div className="flex items-center gap-1.5">
          <Wallet className="w-3 h-3 text-fg-muted" strokeWidth={1.5} aria-hidden />
          <dt className="text-fg-muted">Exposure</dt>
        </div>
        <dd className="text-right text-fg font-medium">
          {row.exposure_usdc > 0
            ? `$${row.exposure_usdc.toLocaleString(undefined, {
                maximumFractionDigits: 0,
              })}`
            : "—"}
        </dd>

        <div className="flex items-center gap-1.5">
          <AlertTriangle
            className="w-3 h-3 text-fg-muted"
            strokeWidth={1.5}
            aria-hidden
          />
          <dt className="text-fg-muted">Open pos</dt>
        </div>
        <dd className="text-right">
          {row.open_count > 0 ? (
            <Link
              href={`/hot/profiles/${encodeURIComponent(row.profile_id)}?tab=positions`}
              className="text-fg hover:text-accent-300 font-medium"
            >
              {row.open_count}
            </Link>
          ) : (
            <span className="text-fg-muted">0</span>
          )}
        </dd>
      </dl>

      <Link
        href={`/hot/profiles/${encodeURIComponent(row.profile_id)}`}
        className="inline-flex items-center justify-center gap-1 text-[11px] text-accent-300 hover:text-accent-200 border-t border-border-subtle pt-2 -mx-3 -mb-3 px-3 pb-2.5 num-tabular"
      >
        open in cockpit
        <ChevronRight className="w-3 h-3" strokeWidth={1.5} aria-hidden />
      </Link>
    </article>
  );
}

function RiskBar({
  label,
  icon,
  currentLabel,
  limitLabel,
  pct,
  danger,
  warn,
}: {
  label: string;
  icon: React.ReactNode;
  currentLabel: string;
  limitLabel: string;
  pct: number;
  danger: boolean;
  warn: boolean;
}) {
  const barColor = danger ? "bg-danger-500" : warn ? "bg-warn-500" : "bg-bid-500";
  const valueColor = danger
    ? "text-danger-500"
    : warn
      ? "text-warn-400"
      : "text-fg";

  return (
    <div className="flex flex-col gap-1">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-1.5 text-[11px] uppercase tracking-wider text-fg-muted">
          <span className="text-fg-muted">{icon}</span>
          <span>{label}</span>
        </div>
        <div className="flex items-baseline gap-1.5 text-[11px] num-tabular">
          <span className={`font-medium ${valueColor}`}>{currentLabel}</span>
          <span className="text-fg-muted/70">/</span>
          <span className="text-fg-muted">{limitLabel}</span>
        </div>
      </div>
      <div className="h-1.5 rounded-full bg-bg-raised overflow-hidden">
        <div
          className={`h-full rounded-full transition-[width] duration-500 ${barColor}`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

export default ProfilesRiskMatrix;
