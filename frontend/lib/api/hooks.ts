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

type QueryOpts<TData> = Omit<UseQueryOptions<TData>, "queryKey" | "queryFn">;

// ---- Query keys (single source of truth for invalidation) ----

export const queryKeys = {
  profiles: ["profiles"] as const,
  positions: (profileId?: string, status: "open" | "all" = "open") =>
    ["positions", profileId ?? "all", status] as const,
  killSwitch: ["killSwitch"] as const,
  candles: (symbol: string, timeframe: string, limit = 500) =>
    ["candles", symbol, timeframe, limit] as const,
  /** Umbrella key — invalidating ["risk"] hits every per-profile query too. */
  risk: ["risk"] as const,
  riskFor: (profileId: string) => ["risk", profileId] as const,
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
  const { limit = 500, ...rest } = opts ?? {};
  return useQuery({
    queryKey: queryKeys.candles(symbol, timeframe, limit),
    queryFn: () => api.marketData.candles(symbol, timeframe, limit),
    enabled: !!symbol,
    ...rest,
  });
}

/** Per-profile risk snapshot (daily PnL, drawdown, allocation). */
export function useRisk(
  profileId: string | undefined,
  opts?: QueryOpts<ProfileRisk>
) {
  return useQuery({
    queryKey: profileId ? queryKeys.riskFor(profileId) : queryKeys.risk,
    queryFn: () => api.agents.risk(profileId as string),
    enabled: !!profileId,
    ...opts,
  });
}

/** Risk snapshots for every profile (the /hot/profiles overview read). */
export function useAllRisk(opts?: QueryOpts<ProfileRisk[]>) {
  return useQuery({
    queryKey: queryKeys.risk,
    queryFn: () => api.agents.allRisk(),
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
