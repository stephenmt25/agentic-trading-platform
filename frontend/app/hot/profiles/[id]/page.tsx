"use client";

import { useCallback, useEffect, useMemo } from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { ChevronLeft } from "lucide-react";

import { Select } from "@/components/primitives";
import { StatusDot } from "@/components/data-display";
import { useClosedTrades, useProfiles, useRisk } from "@/lib/api/hooks";
import { cn } from "@/lib/utils";
import { MetricStrip, type ProfileStrip } from "./_components/MetricStrip";
import { DecisionsTab } from "./_components/DecisionsTab";
import { PositionsTab } from "./_components/PositionsTab";
import { DailyPnlTab } from "./_components/DailyPnlTab";
import { AttributionTab } from "./_components/AttributionTab";

/**
 * /hot/profiles/[id] — per-profile observation cockpit per ADR-018 + spec §9.2.
 *
 * Phase 10.3+ redesign: master-detail with a right-side `DetailDrawer` for
 * row drill-through. The legacy `<DecisionFeed>` / `<PositionsPanel>` are
 * replaced with redesign-native tables that consume the same backends and
 * route row selection through URL query params (`?decision={id}` /
 * `?position={id}`) so drilled views are deep-linkable.
 *
 * Tab state is URL-routed (`?tab=`) with localStorage default per profile.
 */

type Tab = "decisions" | "positions" | "daily-pnl" | "attribution";
const TABS: { id: Tab; label: string }[] = [
  { id: "decisions", label: "Decisions" },
  { id: "positions", label: "Positions" },
  { id: "daily-pnl", label: "Daily P&L" },
  { id: "attribution", label: "Attribution" },
];

const STORAGE_PREFIX = "praxis:profile-cockpit:tab:";
const POLL_INTERVAL_MS = 30_000;

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

function numFrom(rl: Record<string, unknown>, key: string, fb: number): number {
  const v = rl[key];
  if (typeof v === "number" && Number.isFinite(v)) return v;
  if (typeof v === "string") {
    const p = parseFloat(v);
    if (Number.isFinite(p)) return p;
  }
  return fb;
}

export default function ProfileCockpitPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const search = useSearchParams();
  const profileId = decodeURIComponent(params.id);

  // ---- Profile list (shared useProfiles read — FE-W2.1) ----
  const profilesQuery = useProfiles();
  const profiles = useMemo(
    () => profilesQuery.data ?? [],
    [profilesQuery.data]
  );
  const profile = useMemo(
    () => profiles.find((p) => p.profile_id === profileId) ?? null,
    [profiles, profileId]
  );
  const loadError = profilesQuery.error
    ? profilesQuery.error instanceof Error
      ? profilesQuery.error.message
      : "Failed to load profile"
    : profilesQuery.data && !profile
      ? `Profile ${profileId} not found`
      : null;

  // ---- Tab state ----
  const urlTab = search.get("tab") as Tab | null;
  const validTab: Tab | null =
    urlTab && TABS.some((t) => t.id === urlTab) ? urlTab : null;

  useEffect(() => {
    if (validTab) {
      try {
        localStorage.setItem(STORAGE_PREFIX + profileId, validTab);
      } catch {
        // ignore
      }
      return;
    }
    let initial: Tab = "decisions";
    try {
      const saved = localStorage.getItem(STORAGE_PREFIX + profileId) as Tab | null;
      if (saved && TABS.some((t) => t.id === saved)) initial = saved;
    } catch {
      // ignore
    }
    const p = new URLSearchParams(search.toString());
    p.set("tab", initial);
    router.replace(
      `/hot/profiles/${encodeURIComponent(profileId)}?${p.toString()}`
    );
  }, [validTab, profileId, router, search]);

  const activeTab: Tab = validTab ?? "decisions";

  const updateQuery = useCallback(
    (mut: (p: URLSearchParams) => void) => {
      const p = new URLSearchParams(search.toString());
      mut(p);
      router.replace(
        `/hot/profiles/${encodeURIComponent(profileId)}?${p.toString()}`,
        { scroll: false }
      );
    },
    [search, router, profileId]
  );

  const setTab = useCallback(
    (next: Tab) => {
      updateQuery((p) => {
        p.set("tab", next);
        p.delete("decision");
        p.delete("position");
        p.delete("date");
      });
    },
    [updateQuery]
  );

  const selectedDecisionId = search.get("decision");
  const selectedPositionId = search.get("position");
  const selectedDate = search.get("date");

  const setSelectedDecision = useCallback(
    (id: string | null) => {
      updateQuery((p) => {
        if (id) p.set("decision", id);
        else p.delete("decision");
      });
    },
    [updateQuery]
  );

  const setSelectedPosition = useCallback(
    (id: string | null) => {
      updateQuery((p) => {
        if (id) p.set("position", id);
        else p.delete("position");
      });
    },
    [updateQuery]
  );

  const setSelectedDate = useCallback(
    (date: string | null) => {
      updateQuery((p) => {
        if (date) p.set("date", date);
        else p.delete("date");
      });
    },
    [updateQuery]
  );

  // ---- Stat strip aggregation (FE-W2.1: React Query, 30s) ----
  // risk + closed-trades errors degrade gracefully (zeros / null strip),
  // matching the old best-effort `.catch` reads — the banner is owned by
  // the profile fetch above.
  const riskQuery = useRisk(profileId, {
    refetchInterval: POLL_INTERVAL_MS,
    enabled: !!profile,
  });
  const tradesQuery = useClosedTrades(
    { limit: 500 },
    { refetchInterval: POLL_INTERVAL_MS, enabled: !!profile }
  );

  const strip = useMemo<ProfileStrip | null>(() => {
    const trades = tradesQuery.data;
    if (!profile || !trades) return null;
    const risk = riskQuery.data ?? null;

    const ptrades = trades.filter((t) => t.profile_id === profileId);
    const now = new Date();
    const todayTrades = ptrades.filter((t) => isSameUtcDay(t.closed_at, now));
    const wins = todayTrades.filter((t) => t.outcome === "win").length;
    const decided = todayTrades.filter(
      (t) => t.outcome === "win" || t.outcome === "loss"
    ).length;
    const netPnl = ptrades.reduce(
      (acc, t) => acc + (Number.isFinite(t.realized_pnl) ? t.realized_pnl : 0),
      0
    );

    const rl = (profile.risk_limits ?? {}) as Record<string, unknown>;
    const maxAlloc = numFrom(rl, "max_allocation_pct", 0.25);

    return {
      net_pnl_since_boot: netPnl,
      trades_today: todayTrades.length,
      win_rate_today: decided > 0 ? wins / decided : null,
      drawdown_pct: risk?.drawdown_pct ?? 0,
      allocation_pct: risk?.allocation_pct ?? 0,
      max_allocation_pct: maxAlloc,
    };
  }, [profile, profileId, riskQuery.data, tradesQuery.data]);

  const profileOptions = useMemo(
    () =>
      profiles
        .filter((p) => p.is_active)
        .map((p) => ({ value: p.profile_id, label: p.name })),
    [profiles]
  );

  const onSwitchProfile = (nextId: string) => {
    if (nextId === profileId) return;
    const p = new URLSearchParams();
    p.set("tab", activeTab);
    router.push(`/hot/profiles/${encodeURIComponent(nextId)}?${p.toString()}`);
  };

  return (
    <div
      data-mode="cool"
      className="flex flex-col h-full bg-bg-canvas text-fg"
    >
      <header className="shrink-0 border-b border-border-subtle">
        <div className="px-6 pt-3 pb-4 flex flex-col gap-3">
          <Link
            href="/hot/profiles"
            className="inline-flex items-center gap-1 text-[11px] text-fg-muted hover:text-fg w-fit"
          >
            <ChevronLeft className="w-3 h-3" strokeWidth={1.5} aria-hidden />
            All profiles
          </Link>

          <div className="flex items-start justify-between gap-4">
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2.5">
                {profile && (
                  <StatusDot
                    state={profile.is_active ? "live" : "idle"}
                    size={10}
                    pulse={profile.is_active}
                    aria-label={profile.is_active ? "Active" : "Idle"}
                  />
                )}
                <h1 className="text-[20px] font-semibold tracking-tight text-fg truncate">
                  {profile?.name ?? "Loading…"}
                </h1>
              </div>
              <p className="text-[11px] font-mono text-fg-muted mt-1 truncate">
                {profileId}
              </p>
            </div>

            {profileOptions.length > 1 && (
              <Select
                density="compact"
                options={profileOptions}
                value={profileId}
                onValueChange={onSwitchProfile}
                placeholder="Switch profile…"
                className="min-w-[220px] shrink-0"
              />
            )}
          </div>

          {loadError && (
            <div className="rounded-md border border-danger-700/40 bg-danger-700/10 p-2.5 text-[12px] text-danger-500">
              {loadError}
            </div>
          )}

          <MetricStrip strip={strip} />
        </div>

        {/* Tab nav */}
        <nav
          role="tablist"
          aria-label="Profile cockpit tabs"
          className="flex items-center gap-0.5 px-4"
        >
          {TABS.map((t) => {
            const active = activeTab === t.id;
            return (
              <button
                key={t.id}
                role="tab"
                aria-selected={active}
                onClick={() => setTab(t.id)}
                className={cn(
                  "relative h-9 px-3.5 text-[12px] num-tabular",
                  "transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent-500 rounded-t-sm",
                  active ? "text-fg" : "text-fg-secondary hover:text-fg"
                )}
              >
                {t.label}
                {active && (
                  <span
                    aria-hidden
                    className="absolute left-3 right-3 -bottom-px h-0.5 bg-accent-500 rounded-full"
                  />
                )}
              </button>
            );
          })}
        </nav>
      </header>

      {/* Tab body */}
      <div className="flex-1 min-h-0">
        {activeTab === "decisions" && (
          <DecisionsTab
            profileId={profileId}
            selectedId={selectedDecisionId}
            onSelect={setSelectedDecision}
          />
        )}
        {activeTab === "positions" && (
          <PositionsTab
            profileId={profileId}
            selectedId={selectedPositionId}
            onSelect={setSelectedPosition}
          />
        )}
        {activeTab === "daily-pnl" && (
          <DailyPnlTab
            profileId={profileId}
            selectedDate={selectedDate}
            onSelect={setSelectedDate}
          />
        )}
        {activeTab === "attribution" && (
          <AttributionTab profileId={profileId} />
        )}
      </div>
    </div>
  );
}
