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
export type Order = ApiResult<typeof api.orders.list>[number];
export type Candle = ApiResult<typeof api.marketData.candles>[number];
export type ProfileRisk = ApiResult<typeof api.agents.risk>;
export type ClosedTrade = ApiResult<typeof api.audit.closedTrades>[number];
export type KillSwitchState = ApiResult<typeof api.commands.killSwitchStatus>;
export type RiskPortfolio = ApiResult<typeof api.risk.portfolio>;
export type DecaySnapshot = ApiResult<typeof api.risk.decay>;
export type NetOfCost = ApiResult<typeof api.pnl.netOfCost>;
// FE-W2.1 final sweep (debt burn-down F1)
export type PaperStatus = ApiResult<typeof api.paperTrading.status>;
export type DecisionRow = ApiResult<typeof api.paperTrading.decisions>[number];
export type AgentStatusRow = ApiResult<typeof api.agents.status>[number];
export type SessionsPayload = ApiResult<typeof api.sessions.list>;
export type UserEventsPayload = ApiResult<typeof api.audit.userEvents>;
export type BacktestHistoryPayload = ApiResult<typeof api.backtest.history>;
export type BacktestResultPayload = ApiResult<typeof api.backtest.result>;
export type AgentScorePoint = ApiResult<typeof api.agentPerformance.scores>[number];
export type AgentWeightsPayload = ApiResult<typeof api.agentPerformance.weights>;
export type GateAnalyticsPayload = ApiResult<
  typeof api.agentPerformance.gateAnalytics
>;

type QueryOpts<TData> = Omit<UseQueryOptions<TData>, "queryKey" | "queryFn">;

// ---- Query keys (single source of truth for invalidation) ----

export const queryKeys = {
  profiles: ["profiles"] as const,
  positions: (profileId?: string, status: "open" | "all" = "open") =>
    ["positions", profileId ?? "all", status] as const,
  killSwitch: ["killSwitch"] as const,
  orders: (symbol?: string, profileId?: string, limit = 50) =>
    ["orders", symbol ?? "all", profileId ?? "all", limit] as const,
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
  // ---- FE-W2.1 final sweep (debt burn-down F1) ----
  /** Engine-wide /paper-trading/status (EngineTotalsPill + DailyPnlTab). */
  paperTradingStatus: ["paperTradingStatus"] as const,
  /** Trade decisions feed, addressed by profile/outcome/limit. */
  decisions: (profileId?: string, outcome?: string, limit = 100) =>
    ["decisions", profileId ?? "all", outcome ?? "all", limit] as const,
  /** /agents/status — latest per-symbol agent scores. */
  agentStatus: ["agentStatus"] as const,
  /** /auth/sessions — the settings sessions list. */
  sessions: ["sessions"] as const,
  /** /audit/user-events, addressed by the page's filter tuple. */
  auditUserEvents: (
    type: string,
    fromMs?: number,
    toMs?: number,
    limit = 200
  ) => ["auditUserEvents", type, fromMs ?? null, toMs ?? null, limit] as const,
  /** /backtest/history — the run-list read. */
  backtestHistory: (limit = 100) => ["backtestHistory", limit] as const,
  /** /backtest/{job_id} — one job's status payload (live-run polling). */
  backtestResult: (jobId: string) => ["backtestResult", jobId] as const,
  /** /agent-performance/scores/{symbol} (the /analysis overlay read). */
  agentScores: (symbol: string, agents?: string, limit = 2000) =>
    ["agentScores", symbol, agents ?? "all", limit] as const,
  /** /agent-performance/weights/{symbol}. */
  agentWeights: (symbol: string) => ["agentWeights", symbol] as const,
  /** /agent-performance/gate-analytics/{symbol} (AttributionTab). */
  gateAnalytics: (symbol: string, profileId?: string, limit = 500) =>
    ["gateAnalytics", symbol, profileId ?? "all", limit] as const,
  /** /performance surface (F2) — ONE key for its bundled 4-endpoint
   * Promise.all read (weights + gate analytics + weight history +
   * attribution land together, preserving the page's single
   * loading/error state). Own namespace; never aliases ["risk"]. */
  agentPerformance: (symbol: string) => ["agentPerformance", symbol] as const,
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

/**
 * Orders for a symbol (the /hot Open Orders tab read). Polls at 5s so
 * optimistic submissions reconcile against server truth quickly; the
 * interval pauses while the tab is hidden, and React Query stops
 * refetching entirely once the consuming component unmounts. Enabled
 * only when a symbol is present — the "all" slots in the key exist for
 * cache addressing, not for live all-symbols fetches.
 */
export function useOrders(
  params: { symbol?: string; profileId?: string; limit?: number },
  opts?: QueryOpts<Order[]>
) {
  const { symbol, profileId, limit = 50 } = params;
  const { enabled, ...rest } = opts ?? {};
  return useQuery({
    queryKey: queryKeys.orders(symbol, profileId, limit),
    queryFn: () => api.orders.list({ symbol, profileId, limit }),
    refetchInterval: 5_000,
    ...rest,
    enabled: !!symbol && (enabled ?? true),
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

// ---- FE-W2.1 final sweep (debt burn-down F1) ----

/**
 * Engine-wide paper-trading status ("since boot" totals + daily reports).
 * One shared 30s poll for every consumer (EngineTotalsPill lives in chrome
 * on every surface; DailyPnlTab reads the same payload). React Query's
 * dedupe replaces the pill's old in-flight guard, and its abort signal
 * replaces the manual AbortController.
 */
export function usePaperTradingStatus(opts?: QueryOpts<PaperStatus>) {
  return useQuery({
    queryKey: queryKeys.paperTradingStatus,
    queryFn: ({ signal }) => api.paperTrading.status({ signal }),
    refetchInterval: 30_000,
    ...opts,
  });
}

/** Trade decisions for a profile (DecisionsTab). 15s — the tab is the
 * highest-traffic observation surface. */
export function useDecisions(
  params: { profileId?: string; outcome?: string; limit?: number },
  opts?: QueryOpts<DecisionRow[]>
) {
  const { profileId, outcome, limit = 100 } = params;
  return useQuery({
    queryKey: queryKeys.decisions(profileId, outcome, limit),
    queryFn: () =>
      api.paperTrading.decisions({ profile_id: profileId, outcome, limit }),
    refetchInterval: 15_000,
    ...opts,
  });
}

/** Latest per-symbol agent scores (AgentStatusPanel). */
export function useAgentStatus(opts?: QueryOpts<AgentStatusRow[]>) {
  return useQuery({
    queryKey: queryKeys.agentStatus,
    queryFn: () => api.agents.status(),
    refetchInterval: 15_000,
    ...opts,
  });
}

/** Active sessions for the current user (/settings/sessions). */
export function useSessions(opts?: QueryOpts<SessionsPayload>) {
  return useQuery({
    queryKey: queryKeys.sessions,
    queryFn: () => api.sessions.list(),
    refetchInterval: 60_000,
    ...opts,
  });
}

/** User-action audit feed (/settings/audit), keyed by the filter tuple. */
export function useAuditUserEvents(
  params: {
    type: "all" | "kill_switch" | "profile" | "api_key" | "override" | "auth_fail";
    from?: number;
    to?: number;
    limit?: number;
  },
  opts?: QueryOpts<UserEventsPayload>
) {
  const { type, from, to, limit = 200 } = params;
  return useQuery({
    queryKey: queryKeys.auditUserEvents(type, from, to, limit),
    queryFn: () => api.audit.userEvents({ type, from, to, limit }),
    refetchInterval: 30_000,
    ...opts,
  });
}

/** Backtest run history (one-shot; the list page refetches on demand). */
export function useBacktestHistory(
  limit = 100,
  opts?: QueryOpts<BacktestHistoryPayload>
) {
  return useQuery({
    queryKey: queryKeys.backtestHistory(limit),
    queryFn: () => api.backtest.history({ limit }),
    ...opts,
  });
}

/** Agent score series for the /analysis overlay. Callers set the poll. */
export function useAgentScores(
  symbol: string,
  params?: { agents?: string; limit?: number },
  opts?: QueryOpts<AgentScorePoint[]>
) {
  const { agents, limit = 2000 } = params ?? {};
  const { enabled, ...rest } = opts ?? {};
  return useQuery({
    queryKey: queryKeys.agentScores(symbol, agents, limit),
    queryFn: () => api.agentPerformance.scores(symbol, { agents, limit }),
    ...rest,
    enabled: !!symbol && (enabled ?? true),
  });
}

/** Current agent weights + trackers for a symbol. Callers set the poll. */
export function useAgentWeights(
  symbol: string,
  opts?: QueryOpts<AgentWeightsPayload>
) {
  const { enabled, ...rest } = opts ?? {};
  return useQuery({
    queryKey: queryKeys.agentWeights(symbol),
    queryFn: () => api.agentPerformance.weights(symbol),
    ...rest,
    enabled: !!symbol && (enabled ?? true),
  });
}

/** Gate pass/block analytics for a symbol (AttributionTab, 60s). */
export function useGateAnalytics(
  symbol: string,
  params?: { profileId?: string; limit?: number },
  opts?: QueryOpts<GateAnalyticsPayload>
) {
  const { profileId, limit = 500 } = params ?? {};
  const { enabled, ...rest } = opts ?? {};
  return useQuery({
    queryKey: queryKeys.gateAnalytics(symbol, profileId, limit),
    queryFn: () => api.agentPerformance.gateAnalytics(symbol, { profileId, limit }),
    refetchInterval: 60_000,
    ...rest,
    enabled: !!symbol && (enabled ?? true),
  });
}
