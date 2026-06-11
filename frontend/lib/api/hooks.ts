"use client";

/**
 * React Query wrappers for the hot read paths (FE-W0).
 *
 * Every hook keys by [resource, ...args] so concurrent consumers of the
 * same resource collapse to ONE in-flight request (the /hot tabs and the
 * chrome pills read the same data today via independent setInterval polls).
 * Polling migrates to `refetchInterval` — which React Query pauses while
 * the window is unfocused (refetchIntervalInBackground defaults to false),
 * giving the page-visibility guard for free.
 *
 * Migration pattern for the confirmed first-paint bug (positions fetched
 * with an undefined profileId): pass `enabled: !!profileId` so the query
 * waits for the profile to resolve instead of firing a wasted request.
 */

import {
  useQuery,
  type UseQueryOptions,
} from "@tanstack/react-query";
import { api } from "./client";

// ---- Response types, derived from the api client so they can't drift ----

type ApiResult<F extends (...args: never[]) => Promise<unknown>> = Awaited<
  ReturnType<F>
>;

export type Profile = ApiResult<typeof api.profiles.list>[number];
export type Position = ApiResult<typeof api.positions.list>[number];
export type Candle = ApiResult<typeof api.marketData.candles>[number];
export type ProfileRisk = ApiResult<typeof api.agents.risk>;
export type ClosedTrade = ApiResult<typeof api.audit.closedTrades>[number];
export type KillSwitchState = ApiResult<typeof api.commands.killSwitchStatus>;
export type RiskPortfolio = ApiResult<typeof api.risk.portfolio>;
export type DecaySnapshot = ApiResult<typeof api.risk.decay>;
export type NetOfCost = ApiResult<typeof api.pnl.netOfCost>;

type QueryOpts<TData> = Omit<UseQueryOptions<TData>, "queryKey" | "queryFn">;

// ---- Query keys (single source of truth for invalidation) ----

export const queryKeys = {
  profiles: ["profiles"] as const,
  positions: (profileId?: string, status: "open" | "all" = "open") =>
    ["positions", profileId ?? "all", status] as const,
  killSwitch: ["killSwitch"] as const,
  candles: (symbol: string, timeframe: string, limit = 500) =>
    ["candles", symbol, timeframe, limit] as const,
  /**
   * Umbrella PREFIX for invalidation only — invalidateQueries({ queryKey:
   * ["risk"] }) hits allRisk and every per-profile query by prefix. Never
   * used as a live data key: a disabled useRisk(undefined) subscribing to
   * ["risk"] would surface useAllRisk's array through a single-object type.
   */
  risk: ["risk"] as const,
  allRisk: ["risk", "all"] as const,
  riskFor: (profileId: string) => ["risk", "profile", profileId] as const,
  /** PR4 portfolio exposure snapshot — lives under the ["risk"] umbrella
   * prefix so a blanket risk invalidation refreshes it too. */
  riskPortfolio: ["risk", "portfolio"] as const,
  /** PR7 live-vs-backtest decay snapshot. */
  decay: ["risk", "decay"] as const,
  /** PR5 net-of-cost rollup — keyed by window so different windows coexist. */
  netOfCost: (windowHours: number) => ["netOfCost", windowHours] as const,
  closedTrades: (symbol?: string, limit = 500) =>
    ["closedTrades", symbol ?? "all", limit] as const,
};

// ---- Hooks ----

export function useProfiles(opts?: QueryOpts<Profile[]>) {
  return useQuery({
    queryKey: queryKeys.profiles,
    queryFn: () => api.profiles.list(),
    ...opts,
  });
}

/**
 * Open positions, optionally scoped to a profile. Called with `undefined`
 * profileId this fetches ALL positions (the /risk page's read). Per-profile
 * consumers should pass `enabled: !!profileId` to avoid the wasted
 * first-paint request while the active profile is still resolving.
 */
export function usePositions(
  profileId: string | undefined,
  opts?: QueryOpts<Position[]> & { status?: "open" | "all" }
) {
  const { status = "open", ...rest } = opts ?? {};
  return useQuery({
    queryKey: queryKeys.positions(profileId, status),
    queryFn: () => api.positions.list({ status, profileId }),
    ...rest,
  });
}

/**
 * Kill-switch status. Polls by default — this is the safety surface, every
 * consumer should stay live without wiring its own interval. The interval
 * pauses automatically while the tab is hidden.
 */
export function useKillSwitch(opts?: QueryOpts<KillSwitchState>) {
  return useQuery({
    queryKey: queryKeys.killSwitch,
    queryFn: () => api.commands.killSwitchStatus(),
    refetchInterval: 10_000,
    ...opts,
  });
}

export function useCandles(
  symbol: string,
  timeframe = "1h",
  opts?: QueryOpts<Candle[]> & { limit?: number }
) {
  const { limit = 500, enabled, ...rest } = opts ?? {};
  return useQuery({
    queryKey: queryKeys.candles(symbol, timeframe, limit),
    queryFn: () => api.marketData.candles(symbol, timeframe, limit),
    ...rest,
    enabled: !!symbol && (enabled ?? true),
  });
}

/**
 * Per-profile risk snapshot (daily PnL, drawdown, allocation). The
 * profileId guard is merged with (not overridable by) opts.enabled, so a
 * caller can further restrict but never force a fetch of /agents/risk/undefined.
 */
export function useRisk(
  profileId: string | undefined,
  opts?: QueryOpts<ProfileRisk>
) {
  const { enabled, ...rest } = opts ?? {};
  return useQuery({
    queryKey: queryKeys.riskFor(profileId ?? "__pending__"),
    queryFn: () => api.agents.risk(profileId as string),
    ...rest,
    enabled: !!profileId && (enabled ?? true),
  });
}

/** Risk snapshots for every profile (the /hot/profiles overview read). */
export function useAllRisk(opts?: QueryOpts<ProfileRisk[]>) {
  return useQuery({
    queryKey: queryKeys.allRisk,
    queryFn: () => api.agents.allRisk(),
    ...opts,
  });
}

/**
 * PR4 portfolio exposure snapshot (gross vs budget, per-cluster /
 * per-symbol concentration). Polls at the snapshot's own write cadence
 * (10s); pauses while the tab is hidden.
 */
export function useRiskPortfolio(opts?: QueryOpts<RiskPortfolio>) {
  return useQuery({
    queryKey: queryKeys.riskPortfolio,
    queryFn: () => api.risk.portfolio(),
    refetchInterval: 10_000,
    ...opts,
  });
}

/** PR7 per-profile decay reports. Snapshot is written hourly — 60s poll
 * is plenty. */
export function useDecay(opts?: QueryOpts<DecaySnapshot>) {
  return useQuery({
    queryKey: queryKeys.decay,
    queryFn: () => api.risk.decay(),
    refetchInterval: 60_000,
    ...opts,
  });
}

/** PR5 per-profile net-of-cost rollup over a rolling window (hours). */
export function useNetOfCost(windowHours = 168, opts?: QueryOpts<NetOfCost>) {
  return useQuery({
    queryKey: queryKeys.netOfCost(windowHours),
    queryFn: () => api.pnl.netOfCost(windowHours),
    refetchInterval: 60_000,
    ...opts,
  });
}

/**
 * Closed-trades ledger. The backend has no profile filter on this route —
 * consumers that need a per-profile slice should filter via `select` so the
 * 500-row fetch is shared across all of them:
 *
 *   useClosedTrades({}, { select: (rows) =>
 *     rows.filter((r) => r.profile_id === profileId) })
 */
export function useClosedTrades(
  params?: { symbol?: string; limit?: number },
  opts?: QueryOpts<ClosedTrade[]>
) {
  const limit = params?.limit ?? 500;
  return useQuery({
    queryKey: queryKeys.closedTrades(params?.symbol, limit),
    queryFn: () => api.audit.closedTrades({ symbol: params?.symbol, limit }),
    ...opts,
  });
}
