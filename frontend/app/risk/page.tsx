"use client";

import { memo, useMemo } from "react";
import Link from "next/link";
import {
  Shield,
  ShieldAlert,
  AlertTriangle,
  WifiOff,
  Lock,
  Unlock,
  RefreshCw,
} from "lucide-react";

import { Button, Tag } from "@/components/primitives";
import { Pill, StatusDot } from "@/components/data-display";
import { RiskMeter } from "@/components/trading";
import { ProfilesRiskMatrix } from "@/components/risk/ProfilesRiskMatrix";
import { RiskPageSkeleton } from "@/components/risk/RiskPageSkeleton";
import { RiskTruthPanel } from "@/components/risk/RiskTruthPanel";
import {
  type KillSwitchLogEntry,
  type KillSwitchStatus,
  type ProfileResponse,
} from "@/lib/api/client";
import {
  useKillSwitch,
  usePositions,
  useProfiles,
  useRisk,
} from "@/lib/api/hooks";
import { parseHaltLevel, severity, useKillSwitchStore } from "@/lib/stores/killSwitchStore";
import { cn } from "@/lib/utils";

/**
 * /risk — Risk Control surface.
 * Surface spec: docs/design/05-surface-specs/05-risk-control.md.
 *
 * Single-column HOT surface, with the spec's mandate of "legibility over
 * density". Sections in fixed order: kill switch (centerpiece) → exposure
 * → active limits → recent violations.
 *
 * Wired-up vs. Pending split:
 *
 *   Wired:
 *     - Kill switch: useKillSwitch — the shared ["killSwitch"] query that
 *       RedesignShell polls every 10s (zero extra requests from this page).
 *     - Active profile metrics: useRisk(profile_id), 10s refetchInterval.
 *     - Concentration: derived from usePositions (notional / total),
 *       10s refetchInterval.
 *     - Drawdown / daily PnL: agents.risk + portfolioStore.
 *     - Active limits list: profile.risk_limits jsonb.
 *
 *   Pending tags surface where backend reality lags spec:
 *     - Portfolio VaR (no endpoint).
 *     - Recent violations log (no endpoint).
 *     - Auto-flatten progress on hard-arm (no backend wiring).
 *
 * Cmd+Shift+K is now wired globally in RedesignShell — see
 * components/shell/KillSwitchModal.tsx.
 */

const POLL_INTERVAL_MS = 10_000;

interface ActiveLimitsRow {
  key: string;
  label: string;
  unit: "pct" | "x" | "raw" | "hours";
  configured: number;
  current?: number;
  /** When current is unknown (no live source). */
  pending?: boolean;
}

interface ConcentrationEntry {
  symbol: string;
  notional: number;
  pct: number;
}

/** Hoisted out of the useMemo/render path (master-plan perf item) — a new
 * closure per render defeated memoization downstream. */
function numLimit(
  rl: Record<string, unknown>,
  k: string
): number | undefined {
  const v = rl[k];
  if (typeof v === "number" && Number.isFinite(v)) return v;
  if (typeof v === "string") {
    const parsed = parseFloat(v);
    return Number.isFinite(parsed) ? parsed : undefined;
  }
  return undefined;
}

export default function RiskControlPage() {
  const openKillModal = useKillSwitchStore((s) => s.setModalOpen);

  // ---------- Initial profile (row 75: shared useProfiles read — dedupes
  // with ProfilesRiskMatrix's subscription to the same ["profiles"] key;
  // one-shot like the old page-local fetch, not a poller) ----------
  const profilesQuery = useProfiles();
  const profile = useMemo<ProfileResponse | null>(() => {
    const all = profilesQuery.data ?? [];
    return all.find((p) => p.is_active) ?? all[0] ?? null;
  }, [profilesQuery.data]);
  const profileLoading = profilesQuery.isPending;
  const profileError = profilesQuery.error
    ? profilesQuery.error instanceof Error
      ? profilesQuery.error.message
      : "Failed to load profiles"
    : null;

  // ---------- Live reads (FE-W2: React Query, no page-local setInterval) ----
  // Same fetches reloadAll made — api.agents.risk(profile_id) and
  // api.positions.list({ status: "open" }) — now on a 10s refetchInterval
  // that stops on unmount and pauses while the tab is hidden. Errors keep
  // the last good data instead of zeroing the page.
  const riskQuery = useRisk(profile?.profile_id, {
    refetchInterval: POLL_INTERVAL_MS,
  });
  const positionsQuery = usePositions(undefined, {
    status: "open",
    refetchInterval: POLL_INTERVAL_MS,
  });
  const riskMetrics = riskQuery.data ?? null;

  const { concentration, openCount } = useMemo<{
    concentration: ConcentrationEntry[];
    openCount: number;
  }>(() => {
    const open = (positionsQuery.data ?? []).filter(
      (p) => p.status?.toLowerCase() === "open"
    );
    const totalNotional = open.reduce((acc, p) => {
      const n = parseFloat(p.notional ?? "0");
      return acc + (Number.isFinite(n) ? Math.abs(n) : 0);
    }, 0);
    if (totalNotional <= 0) {
      return { concentration: [], openCount: open.length };
    }
    const bySymbol = new Map<string, number>();
    for (const p of open) {
      const n = parseFloat(p.notional ?? "0");
      if (!Number.isFinite(n)) continue;
      bySymbol.set(p.symbol, (bySymbol.get(p.symbol) ?? 0) + Math.abs(n));
    }
    const entries: ConcentrationEntry[] = [...bySymbol.entries()]
      .map(([symbol, notional]) => ({
        symbol,
        notional,
        pct: notional / totalNotional,
      }))
      .sort((a, b) => b.notional - a.notional);
    return { concentration: entries, openCount: open.length };
  }, [positionsQuery.data]);

  // ---------- Kill switch ----------
  // Shared ["killSwitch"] query — RedesignShell owns the single 10s network
  // poll AND the killSwitchStore mirror; subscribing here adds zero extra
  // requests. isPending is initial-load only (no per-poll flash).
  const killQuery = useKillSwitch();
  const killStatus = killQuery.data ?? null;
  const killLoading = killQuery.isPending;

  // ---------- Active limits derivation ----------
  const activeLimits = useMemo<ActiveLimitsRow[]>(() => {
    if (!profile) return [];
    const rl = (profile.risk_limits ?? {}) as Record<string, unknown>;
    const num = (k: string) => numLimit(rl, k);
    const rows: ActiveLimitsRow[] = [];
    const maxAlloc = num("max_allocation_pct");
    if (maxAlloc !== undefined) {
      rows.push({
        key: "max_allocation_pct",
        label: "Max trade size (per-trade × confidence)",
        unit: "pct",
        configured: maxAlloc,
        current: riskMetrics?.allocation_pct,
      });
    }
    const stopLoss = num("stop_loss_pct");
    if (stopLoss !== undefined) {
      rows.push({
        key: "stop_loss_pct",
        label: "Stop loss",
        unit: "pct",
        configured: stopLoss,
        pending: true,
      });
    }
    const takeProfit = num("take_profit_pct");
    if (takeProfit !== undefined) {
      rows.push({
        key: "take_profit_pct",
        label: "Take profit",
        unit: "pct",
        configured: takeProfit,
        pending: true,
      });
    }
    const maxDD = num("max_drawdown_pct");
    if (maxDD !== undefined) {
      rows.push({
        key: "max_drawdown_pct",
        label: "Max drawdown",
        unit: "pct",
        configured: maxDD,
        current: riskMetrics?.drawdown_pct,
      });
    }
    const cbDaily = num("circuit_breaker_daily_loss_pct");
    if (cbDaily !== undefined) {
      rows.push({
        key: "circuit_breaker_daily_loss_pct",
        label: "Daily loss circuit breaker",
        unit: "pct",
        configured: cbDaily,
        current:
          riskMetrics?.daily_pnl_pct !== undefined
            ? Math.max(0, -riskMetrics.daily_pnl_pct)
            : undefined,
      });
    }
    const maxHold = num("max_holding_hours");
    if (maxHold !== undefined) {
      rows.push({
        key: "max_holding_hours",
        label: "Max hold duration",
        unit: "hours",
        configured: maxHold,
        pending: true,
      });
    }
    return rows;
  }, [profile, riskMetrics]);

  // Initial load → skeleton mirroring the page layout (FE-W1) instead of
  // the previous empty-state pop.
  if (profileLoading && !profile) {
    return <RiskPageSkeleton />;
  }

  return (
    <div data-mode="hot" className="flex flex-col h-full bg-bg-canvas text-fg">
      {/* Header */}
      <header className="flex items-start justify-between gap-4 border-b border-border-subtle px-6 py-4">
        <div className="min-w-0">
          <div className="flex items-center gap-2 text-[12px] text-fg-muted">
            <Shield className="w-3.5 h-3.5" strokeWidth={1.5} aria-hidden />
            <span className="num-tabular">Risk Control</span>
          </div>
          <h1 className="text-[18px] font-semibold tracking-tight text-fg mt-1.5">
            {profile ? profile.name : "—"}
          </h1>
          <p className="text-[12px] text-fg-muted mt-0.5 num-tabular">
            {riskMetrics
              ? formatHeaderSummary(riskMetrics, openCount)
              : "Live metrics not loaded"}
          </p>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <Button
            intent="secondary"
            size="sm"
            leftIcon={<RefreshCw className="w-3 h-3" strokeWidth={1.5} />}
            onClick={() => {
              killQuery.refetch();
              riskQuery.refetch();
              positionsQuery.refetch();
            }}
          >
            Refresh
          </Button>
        </div>
      </header>

      {/* Banners */}
      {profileError && (
        <Banner
          tone="danger"
          icon={<WifiOff className="w-4 h-4" strokeWidth={1.5} />}
          title="Profiles unreachable"
          body={profileError}
        />
      )}
      {!profileLoading && !profile && !profileError && (
        <Banner
          tone="warn"
          icon={<AlertTriangle className="w-4 h-4" strokeWidth={1.5} />}
          title="No active profile"
          body={
            <>
              Risk Control monitors live trading. Activate a profile in{" "}
              <Link
                href="/canvas"
                className="text-accent-300 hover:text-accent-200 underline"
              >
                Pipeline Canvas
              </Link>{" "}
              to see live risk.
            </>
          }
        />
      )}

      <div className="flex-1 min-h-0 overflow-auto">
        <div className="px-6 py-6 flex flex-col gap-6 max-w-4xl">
          <ProfilesRiskMatrix />

          <KillSwitchSection
            status={killStatus}
            loading={killLoading}
            onOpenModal={() => openKillModal(true)}
          />

          <ExposureSection
            riskMetrics={riskMetrics}
            concentration={concentration}
            openCount={openCount}
            allocationLimitPct={
              ((profile?.risk_limits as Record<string, unknown> | undefined)?.[
                "max_allocation_pct"
              ] as number | undefined) ?? 1
            }
          />

          <RiskTruthPanel />

          <ActiveLimitsSection rows={activeLimits} profile={profile} />

          <ViolationsSection killStatus={killStatus} />
        </div>
      </div>
    </div>
  );
}

/* -------------------------- Header summary -------------------------------- */

function formatHeaderSummary(
  m: { daily_pnl_pct: number; drawdown_pct: number; allocation_pct: number },
  openCount: number
): string {
  const pnl = `pnl 24h ${m.daily_pnl_pct >= 0 ? "+" : ""}${(
    m.daily_pnl_pct * 100
  ).toFixed(2)}%`;
  const dd = `drawdown ${(m.drawdown_pct * 100).toFixed(2)}%`;
  const alloc = `allocation ${(m.allocation_pct * 100).toFixed(0)}%`;
  return `${pnl} · ${dd} · ${alloc} · ${openCount} open`;
}

/* -------------------------- Kill switch ----------------------------------- */

interface KillSwitchSectionProps {
  status: KillSwitchStatus | null;
  loading: boolean;
  onOpenModal: () => void;
}

function KillSwitchSection({
  status,
  loading,
  onOpenModal,
}: KillSwitchSectionProps) {
  const isArmed = status?.active === true;
  const level = parseHaltLevel(status?.level, status?.active);
  // NEUTRALIZE/FLATTEN are position-destructive — the panel must show the
  // same danger tier as StatusPills and the body overlay, not warn-yellow.
  const isDanger = isArmed && severity(level) === "danger";
  const stateLabel = isArmed ? `HALTED (${level})` : "TRADING NORMAL";
  const lastEvent = status?.recent_log?.[0];

  return (
    <Section title="KILL SWITCH" topOfFold>
      <div
        className={cn(
          "rounded-md border-2 p-5 flex flex-col gap-4",
          isDanger
            ? "border-danger-500 bg-danger-500/10"
            : isArmed
              ? "border-warn-500 bg-warn-500/10"
              : "border-border-subtle bg-bg-panel"
        )}
        data-state={isArmed ? `halted-${level.toLowerCase()}` : "off"}
      >
        <div className="flex items-start gap-4 justify-between">
          <div className="flex items-center gap-3">
            <span
              aria-hidden
              className={cn(
                "w-12 h-12 rounded-full flex items-center justify-center",
                isDanger
                  ? "bg-danger-500/20"
                  : isArmed
                    ? "bg-warn-500/20"
                    : "bg-bg-raised"
              )}
            >
              {isArmed ? (
                <ShieldAlert
                  className={cn(
                    "w-6 h-6",
                    isDanger ? "text-danger-500" : "text-warn-500"
                  )}
                  strokeWidth={1.5}
                  aria-hidden
                />
              ) : (
                <Shield
                  className="w-6 h-6 text-fg-muted"
                  strokeWidth={1.5}
                  aria-hidden
                />
              )}
            </span>
            <div>
              <p
                className={cn(
                  "text-[20px] font-semibold tracking-tight num-tabular",
                  isDanger
                    ? "text-danger-500"
                    : isArmed
                      ? "text-warn-500"
                      : "text-fg"
                )}
                aria-live="polite"
              >
                {loading ? "—" : stateLabel}
              </p>
              {lastEvent && (
                <p className="text-[12px] text-fg-muted mt-0.5 num-tabular">
                  {lastEvent.action} {formatRelative(lastEvent.timestamp)} by{" "}
                  <span className="font-mono">{entryActor(lastEvent)}</span>
                  {lastEvent.reason && (
                    <>
                      {" "}
                      · reason: <span className="italic">&ldquo;{lastEvent.reason}&rdquo;</span>
                    </>
                  )}
                </p>
              )}
            </div>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            {isArmed ? (
              <Button
                intent="secondary"
                size="md"
                leftIcon={<Unlock className="w-3.5 h-3.5" strokeWidth={1.5} />}
                onClick={onOpenModal}
                data-testid="kill-switch-open"
              >
                Adjust / resume
              </Button>
            ) : (
              <Button
                intent="primary"
                size="md"
                leftIcon={<Lock className="w-3.5 h-3.5" strokeWidth={1.5} />}
                onClick={onOpenModal}
                data-testid="kill-switch-open"
              >
                Halt trading…
              </Button>
            )}
          </div>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-[12px] text-fg-secondary">
          <div className="flex items-start gap-2">
            <StatusDot state="warn" size={6} />
            <span>
              <strong className="text-fg">STOP_OPENING / DE_RISK</strong>: block
              new entries; DE_RISK also cancels resting orders and halts
              averaging-in. Positions stay open.
            </span>
          </div>
          <div className="flex items-start gap-2">
            <StatusDot state="armed" size={6} />
            <span>
              <strong className="text-fg">NEUTRALIZE / FLATTEN</strong>:
              reduce-only trims to ≤50% gross budget; FLATTEN closes ALL
              positions (two-step confirm in the halt control).
            </span>
          </div>
        </div>
        <p className="text-[11px] text-fg-muted">
          <kbd className="px-1 py-0.5 rounded-sm bg-bg-raised border border-border-subtle font-mono text-[10px]">
            Cmd+Shift+K
          </kbd>{" "}
          to toggle from any surface
        </p>
      </div>
    </Section>
  );
}

/* -------------------------- Exposure -------------------------------------- */

interface ExposureSectionProps {
  riskMetrics: {
    daily_pnl_pct: number;
    drawdown_pct: number;
    allocation_pct: number;
  } | null;
  concentration: ConcentrationEntry[];
  openCount: number;
  allocationLimitPct: number;
}

function ExposureSection({
  riskMetrics,
  concentration,
  openCount,
  allocationLimitPct,
}: ExposureSectionProps) {
  return (
    <Section title="EXPOSURE">
      <div className="rounded-md border border-border-subtle bg-bg-panel p-5 flex flex-col gap-5">
        <div>
          <div className="flex items-center justify-between mb-1.5">
            <span className="text-[12px] uppercase tracking-wider text-fg-muted num-tabular">
              Allocation utilization
            </span>
            <Tag intent="warn">leverage Pending</Tag>
          </div>
          {riskMetrics ? (
            <RiskMeter
              kind="custom"
              label="Allocation %"
              value={(riskMetrics.allocation_pct ?? 0) * 100}
              max={Math.max(allocationLimitPct, 0.0001) * 100}
              unit="%"
            />
          ) : (
            <p className="text-[12px] text-fg-muted">
              Live allocation not yet loaded.
            </p>
          )}
          <p className="text-[10px] text-fg-muted mt-1.5">
            Backend exposes allocation %, not leverage × — leverage meter waits
            on services/risk.
          </p>
        </div>

        <div>
          <div className="flex items-center justify-between mb-1.5">
            <span className="text-[12px] uppercase tracking-wider text-fg-muted num-tabular">
              Drawdown (current)
            </span>
            <Tag intent="warn">VaR Pending</Tag>
          </div>
          {riskMetrics ? (
            <RiskMeter
              kind="drawdown"
              value={Math.abs(riskMetrics.drawdown_pct ?? 0) * 100}
              max={20}
              unit="%"
            />
          ) : (
            <p className="text-[12px] text-fg-muted">
              Drawdown not yet loaded.
            </p>
          )}
          <p className="text-[10px] text-fg-muted mt-1.5">
            VaR (1d, 95%) needs a dedicated endpoint — surfacing drawdown for
            now.
          </p>
        </div>

        <div>
          <div className="flex items-center justify-between mb-1.5">
            <span className="text-[12px] uppercase tracking-wider text-fg-muted num-tabular">
              Concentration ({openCount} open)
            </span>
          </div>
          {concentration.length === 0 ? (
            <p className="text-[12px] text-fg-muted">
              No positions — exposure is zero.
            </p>
          ) : (
            <ConcentrationBar entries={concentration.slice(0, 6)} />
          )}
        </div>
      </div>
    </Section>
  );
}

function ConcentrationBar({ entries }: { entries: ConcentrationEntry[] }) {
  return (
    <div className="flex flex-col gap-2">
      <div className="relative h-3 rounded-sm overflow-hidden bg-bg-raised flex">
        {entries.map((e, i) => (
          <span
            key={e.symbol}
            className={cn(
              "h-full",
              i === 0 ? "bg-fg" : i === 1 ? "bg-fg/70" : "bg-fg/40"
            )}
            style={{ width: `${(e.pct * 100).toFixed(2)}%` }}
            aria-label={`${e.symbol} ${(e.pct * 100).toFixed(0)}%`}
          />
        ))}
      </div>
      <ul className="flex flex-wrap gap-x-4 gap-y-1 text-[12px] num-tabular text-fg-secondary">
        {entries.map((e) => (
          <li key={e.symbol} className="flex items-center gap-1.5">
            <span className="font-mono text-fg">{e.symbol}</span>
            <span className="text-fg-muted">
              {(e.pct * 100).toFixed(0)}%
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

/* -------------------------- Active limits --------------------------------- */

function ActiveLimitsSection({
  rows,
  profile,
}: {
  rows: ActiveLimitsRow[];
  profile: ProfileResponse | null;
}) {
  return (
    <Section title="ACTIVE LIMITS">
      <div className="rounded-md border border-border-subtle bg-bg-panel">
        {rows.length === 0 ? (
          <p className="px-5 py-4 text-[12px] text-fg-muted">
            No risk limits configured for this profile.
          </p>
        ) : (
          <ul className="divide-y divide-border-subtle">
            {rows.map((row) => (
              <ActiveLimitRow key={row.key} row={row} profile={profile} />
            ))}
          </ul>
        )}
      </div>
    </Section>
  );
}

/** Memoized (FE-W1 perf item): the 10s poll re-renders the page; rows whose
 * props are unchanged must not update. */
const ActiveLimitRow = memo(function ActiveLimitRow({
  row,
  profile,
}: {
  row: ActiveLimitsRow;
  profile: ProfileResponse | null;
}) {
  const utilization =
    row.current !== undefined && row.configured > 0
      ? row.current / row.configured
      : null;

  let dotState: "live" | "idle" | "warn" | "error" = "idle";
  if (utilization !== null) {
    if (utilization >= 0.85) dotState = "error";
    else if (utilization >= 0.6) dotState = "warn";
    else dotState = "live";
  }

  return (
    <li className="flex items-center gap-3 px-5 py-3">
      <StatusDot state={dotState} size={8} />
      <div className="flex-1 min-w-0">
        <p className="text-[13px] text-fg num-tabular">{row.label}</p>
        <p className="text-[11px] text-fg-muted num-tabular font-mono">
          configured: {formatLimit(row.configured, row.unit)}
          {row.current !== undefined && (
            <>
              {" · current: "}
              {formatLimit(row.current, row.unit)}
              {utilization !== null && (
                <>
                  {" · "}
                  {(utilization * 100).toFixed(0)}% utilized
                </>
              )}
            </>
          )}
          {row.pending && (
            <>
              {" · "}
              <Tag intent="warn">live value Pending</Tag>
            </>
          )}
        </p>
      </div>
      <Link
        href={profile ? `/canvas/${encodeURIComponent(profile.profile_id)}` : "/canvas"}
        className="text-[11px] text-accent-300 hover:text-accent-200 shrink-0 num-tabular"
      >
        edit ▸
      </Link>
    </li>
  );
});

function formatLimit(value: number, unit: ActiveLimitsRow["unit"]): string {
  switch (unit) {
    case "pct":
      return `${(value * 100).toFixed(2)}%`;
    case "x":
      return `${value.toFixed(1)}×`;
    case "hours":
      return `${value.toFixed(0)}h`;
    case "raw":
    default:
      return value.toLocaleString();
  }
}

/* -------------------------- Violations ------------------------------------ */

function ViolationsSection({ killStatus }: { killStatus: KillSwitchStatus | null }) {
  const log = killStatus?.recent_log ?? [];
  return (
    <Section title="RECENT VIOLATIONS">
      <div className="rounded-md border border-border-subtle bg-bg-panel">
        <div className="px-5 py-3 border-b border-border-subtle flex items-center gap-2">
          <Tag intent="warn">Pending</Tag>
          <span className="text-[11px] text-fg-muted">
            Order rejections + warning stream not yet exposed by services/risk.
            Showing kill-switch transitions only.
          </span>
        </div>
        {log.length === 0 ? (
          <p className="px-5 py-6 text-[12px] text-fg-muted">
            No violations recorded. Limits are working as configured.
          </p>
        ) : (
          <ul className="divide-y divide-border-subtle">
            {log.map((entry, i) => (
              <li
                key={`${entry.timestamp}-${i}`}
                className="px-5 py-2.5 text-[12px] text-fg num-tabular flex items-baseline gap-3"
              >
                <span className="font-mono text-fg-muted">
                  {formatTime(entry.timestamp)}
                </span>
                <Pill
                  intent={
                    // Halt-engaging actions only: "DEACTIVATED" contains the
                    // substring "ACTIVATED", so the verb must be anchored.
                    /^(ACTIVATED$|SET_(?!NONE))/i.test(entry.action)
                      ? "warn"
                      : "neutral"
                  }
                >
                  kill-switch {entry.action}
                </Pill>
                <span className="text-fg-secondary truncate flex-1">
                  by {entryActor(entry)}
                  {entry.reason && (
                    <>
                      {" · "}
                      <span className="italic">&ldquo;{entry.reason}&rdquo;</span>
                    </>
                  )}
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </Section>
  );
}

/* -------------------------- Shared --------------------------------------- */

function Section({
  title,
  topOfFold,
  children,
}: {
  title: string;
  topOfFold?: boolean;
  children: React.ReactNode;
}) {
  return (
    <section
      data-top-of-fold={topOfFold || undefined}
      className="flex flex-col gap-2"
    >
      <h2 className="text-[10px] uppercase tracking-wider text-fg-muted num-tabular">
        {title}
      </h2>
      {children}
    </section>
  );
}

function Banner({
  tone,
  icon,
  title,
  body,
}: {
  tone: "warn" | "danger";
  icon: React.ReactNode;
  title: string;
  body: React.ReactNode;
}) {
  const toneClass =
    tone === "danger"
      ? "border-danger-700/40 bg-danger-700/10 text-danger-500"
      : "border-warn-700/40 bg-warn-700/10 text-warn-400";
  return (
    <div role="alert" className={cn("mx-6 mt-4 rounded-md border p-3 flex items-start gap-3 text-[12px]", toneClass)}>
      <span className="shrink-0 mt-0.5" aria-hidden>
        {icon}
      </span>
      <div className="flex-1">
        <p className="font-medium">{title}</p>
        <p className="text-fg-muted mt-0.5">{body}</p>
      </div>
    </div>
  );
}

/** Log writers vary by era: set_level writes `actor`, the legacy paths
 * wrote `activated_by`/`deactivated_by`. */
function entryActor(e: KillSwitchLogEntry): string {
  return e.actor ?? e.activated_by ?? e.deactivated_by ?? "system";
}

/** Backend log timestamps are epoch SECONDS (time.time()); older shapes
 * could be ISO strings. Returns ms or null. */
function tsToMs(ts: number | string | null | undefined): number | null {
  if (typeof ts === "number" && Number.isFinite(ts)) return ts * 1000;
  if (typeof ts === "string") {
    const t = Date.parse(ts);
    return Number.isFinite(t) ? t : null;
  }
  return null;
}

function formatRelative(ts: number | string | null | undefined): string {
  const t = tsToMs(ts);
  if (t === null) return "—";
  const diff = Date.now() - t;
  if (diff < 60_000) return `${Math.floor(diff / 1000)}s ago`;
  if (diff < 3_600_000) return `${Math.floor(diff / 60_000)}m ago`;
  if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)}h ago`;
  return `${Math.floor(diff / 86_400_000)}d ago`;
}

function formatTime(ts: number | string | null | undefined): string {
  const t = tsToMs(ts);
  if (t === null) return "—";
  return new Date(t).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
  });
}
