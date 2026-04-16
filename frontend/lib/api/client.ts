/**
 * Typed API client for the Agentic Trading Platform backend.
 *
 * Auto-attaches the NextAuth.js session JWT as an Authorization header.
 * Redirects to /login on 401 responses.
 */

import { z } from "zod";
import { useConnectionStore } from "../stores/connectionStore";

// REST calls: on Vercel, use the same-origin rewrite proxy (/api/backend) to
// avoid CORS.  In local dev, hit the backend directly on localhost.
const IS_VERCEL = process.env.VERCEL === "1";
const API_BASE_URL =
  typeof window !== "undefined" && IS_VERCEL
    ? "/api/backend"
    : process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// Direct backend URL — used only for WebSocket connections (Vercel can't proxy WS).
export const BACKEND_DIRECT_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export class BackendUnreachableError extends Error {
  constructor() {
    super("Backend is not reachable");
    this.name = "BackendUnreachableError";
  }
}

interface ApiClientOptions extends Omit<RequestInit, "body"> {
  body?: unknown;
}

async function getSessionToken(): Promise<string | null> {
  if (typeof window === "undefined") return null;

  try {
    const res = await fetch("/api/auth/session");
    const session = await res.json();
    return session?.accessToken || null;
  } catch {
    return null;
  }
}

async function apiRequest<T>(
  endpoint: string,
  options: ApiClientOptions = {}
): Promise<T> {
  const { body, headers: customHeaders, ...rest } = options;

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(customHeaders as Record<string, string>),
  };

  const token = await getSessionToken();
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const config: RequestInit = {
    ...rest,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  };

  // FastAPI expects trailing slashes — without them it returns a 307 redirect
  // whose response lacks CORS headers, causing browser fetch to fail.
  const normalizedEndpoint =
    endpoint.endsWith("/") || endpoint.includes("?") ? endpoint : `${endpoint}/`;

  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${normalizedEndpoint}`, config);
  } catch {
    // Network error — backend unreachable (no response at all)
    useConnectionStore.getState().recordFailure();
    throw new BackendUnreachableError();
  }

  // Got a response — backend is reachable
  useConnectionStore.getState().recordSuccess();

  if (response.status === 401) {
    // Don't redirect here — the AppShell already handles session-based redirects.
    // Redirecting on API 401 causes a loop when the backend token isn't ready yet.
    throw new Error("Unauthorized — backend rejected the request");
  }

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "Unknown error" }));
    throw new Error(error.detail || `API Error: ${response.status}`);
  }

  return response.json() as Promise<T>;
}

/**
 * Validated API request -- parses the response through a Zod schema to ensure
 * the backend returned the expected shape.
 */
async function validatedRequest<T>(
  schema: z.ZodType<T>,
  endpoint: string,
  options: ApiClientOptions = {}
): Promise<T> {
  const raw = await apiRequest<unknown>(endpoint, options);
  return schema.parse(raw);
}

// ---- Zod Schemas for critical responses ----

const ExchangeKeyInfoSchema = z.object({
  id: z.string(),
  exchange_name: z.string(),
  label: z.string(),
  is_active: z.boolean(),
  created_at: z.string(),
});

const TestConnectionResponseSchema = z.object({
  status: z.string(),
  message: z.string(),
});

const ProfileResponseSchema = z.object({
  profile_id: z.string(),
  name: z.string(),
  is_active: z.boolean(),
  rules_json: z.record(z.string(), z.unknown()),
  allocation_pct: z.coerce.number(),
  created_at: z.string(),
  deleted_at: z.string().nullable(),
});

const BacktestResultSchema = z.object({
  job_id: z.string().optional(),
  status: z.string(),
}).passthrough();

// ---- Type Definitions ----

export interface ExchangeKeyInfo {
  id: string;
  exchange_name: string;
  label: string;
  is_active: boolean;
  created_at: string;
}

export interface TestConnectionResponse {
  status: string;
  message: string;
}

export interface StoreKeyResponse {
  id: string;
  exchange_name: string;
  label: string;
  message: string;
}

export interface ProfileResponse {
  profile_id: string;
  name: string;
  is_active: boolean;
  rules_json: Record<string, unknown>;
  allocation_pct: number;
  created_at: string;
  deleted_at: string | null;
}

export interface KillSwitchStatus {
  active: boolean;
  recent_log: Array<{
    action: string;
    reason: string;
    by: string;
    timestamp: string;
  }>;
}

export interface KillSwitchToggleResponse {
  status: string;
  reason: string | null;
}

export interface TradingModeStatus {
  trading_enabled: boolean;
  paper_trading_mode: boolean;
  binance_testnet: boolean;
  coinbase_sandbox: boolean;
  effective_mode: "PAPER" | "TESTNET" | "LIVE";
}

export interface PaperTradingStatus {
  days_elapsed: number;
  target_days: number;
  start_date: string | null;
  metrics: {
    total_trades: number;
    avg_win_rate: number;
    total_gross_pnl: number;
    total_net_pnl: number;
    max_drawdown: number;
    avg_sharpe: number;
  };
  daily_reports: Array<{
    id: number;
    report_date: string;
    total_trades: number;
    win_rate: number;
    gross_pnl: number;
    net_pnl: number;
    max_drawdown: number;
    sharpe_ratio: number;
  }>;
}

export interface TradeDecision {
  event_id: string;
  profile_id: string;
  symbol: string;
  outcome: string;
  input_price: number;
  input_volume: number | null;
  indicators: {
    rsi: number; macd_line: number; signal_line: number; histogram: number;
    atr: number; adx: number | null; bb_upper: number | null; bb_lower: number | null;
    bb_pct_b: number | null; obv: number | null; choppiness: number | null;
  };
  strategy: {
    direction: string; logic: string; base_confidence: number; matched: boolean;
    conditions: Array<{ indicator: string; operator: string; threshold: number; actual_value: number; passed: boolean }>;
  };
  regime: {
    rule_based: string | null; hmm: string | null; resolved: string | null;
    confidence_multiplier: number;
  } | null;
  agents: {
    ta: { score: number | null; weight: number; adjustment: number } | null;
    sentiment: { score: number | null; weight: number; adjustment: number } | null;
    debate: { score: number | null; weight: number; adjustment: number } | null;
    confidence_before: number; confidence_after: number;
  } | null;
  gates: Record<string, { passed: boolean; reason?: string; [key: string]: unknown }>;
  profile_rules: Record<string, unknown>;
  order_id: string | null;
  created_at: string;
}

// ---- Typed API Methods ----

export const api = {
  profiles: {
    list: () =>
      validatedRequest(z.array(ProfileResponseSchema), "/profiles"),

    create: (data: {
      name: string;
      rules_json: Record<string, unknown>;
      risk_limits?: Record<string, unknown>;
      allocation_pct?: number;
    }) =>
      apiRequest<{ status: string; id: string; profile: ProfileResponse }>("/profiles", {
        method: "POST",
        body: data,
      }),

    update: (profileId: string, data: {
      rules_json: Record<string, unknown>;
      is_active?: boolean;
    }) =>
      apiRequest<{ status: string; profile: ProfileResponse }>(`/profiles/${profileId}`, {
        method: "PUT",
        body: data,
      }),

    toggle: (profileId: string, isActive: boolean) =>
      apiRequest<{ status: string; is_active: boolean }>(`/profiles/${profileId}/toggle`, {
        method: "PATCH",
        body: { is_active: isActive },
      }),

    delete: (profileId: string) =>
      apiRequest<{ status: string }>(`/profiles/${profileId}`, {
        method: "DELETE",
      }),
  },

  paperTrading: {
    status: () =>
      apiRequest<PaperTradingStatus>("/paper-trading/status"),

    mode: () =>
      apiRequest<TradingModeStatus>("/paper-trading/mode"),

    decisions: (params?: { profile_id?: string; symbol?: string; outcome?: string; limit?: number; offset?: number }) => {
      const qs = new URLSearchParams();
      if (params?.profile_id) qs.set("profile_id", params.profile_id);
      if (params?.symbol) qs.set("symbol", params.symbol);
      if (params?.outcome) qs.set("outcome", params.outcome);
      if (params?.limit) qs.set("limit", String(params.limit));
      if (params?.offset) qs.set("offset", String(params.offset));
      const query = qs.toString();
      return apiRequest<TradeDecision[]>(`/paper-trading/decisions${query ? `?${query}` : ""}`);
    },

    decision: (eventId: string) =>
      apiRequest<TradeDecision>(`/paper-trading/decisions/${eventId}`),
  },

  commands: {
    killSwitchStatus: () =>
      apiRequest<KillSwitchStatus>("/commands/kill-switch"),

    killSwitchToggle: (active: boolean, reason?: string) =>
      apiRequest<KillSwitchToggleResponse>("/commands/kill-switch", {
        method: "POST",
        body: { active, reason },
      }),
  },

  exchangeKeys: {
    list: () =>
      validatedRequest(z.array(ExchangeKeyInfoSchema), "/exchange-keys"),

    store: (data: {
      exchange_id: string;
      api_key: string;
      api_secret: string;
    }) =>
      apiRequest<StoreKeyResponse>("/exchange-keys", {
        method: "POST",
        body: data,
      }),

    test: (data: {
      api_key: string;
      api_secret: string;
      exchange_id: string;
    }) =>
      validatedRequest(TestConnectionResponseSchema, "/exchange-keys/test", {
        method: "POST",
        body: data,
      }),

    delete: (id: string) =>
      apiRequest<{ message: string; id: string }>(`/exchange-keys/${id}`, {
        method: "DELETE",
      }),
  },

  backtest: {
    submit: (data: {
      symbol: string;
      strategy_rules: Record<string, unknown>;
      start_date: string;
      end_date: string;
      slippage_pct: number;
    }) =>
      apiRequest<{ job_id: string; status: string }>("/backtest", {
        method: "POST",
        body: data,
      }),

    result: (jobId: string) =>
      validatedRequest(BacktestResultSchema, `/backtest/${jobId}`),
  },

  agents: {
    status: () =>
      apiRequest<Array<{
        symbol: string;
        ta_score: number | null;
        sentiment_score: number | null;
        sentiment_confidence: number | null;
        sentiment_source: string | null;
        hmm_regime: string | null;
        hmm_state_index: number | null;
      }>>("/agents/status"),

    risk: (profileId: string) =>
      apiRequest<{
        profile_id: string;
        daily_pnl_pct: number;
        drawdown_pct: number;
        allocation_pct: number;
      }>(`/agents/risk/${profileId}`),

    allRisk: () =>
      apiRequest<Array<{
        profile_id: string;
        daily_pnl_pct: number;
        drawdown_pct: number;
        allocation_pct: number;
      }>>("/agents/risk"),
  },

  preferences: {
    get: () =>
      apiRequest<{
        email_alerts: boolean;
        trade_notifications: boolean;
        default_exchange: string;
        timezone: string;
      }>("/preferences"),

    save: (data: {
      email_alerts: boolean;
      trade_notifications: boolean;
      default_exchange: string;
      timezone: string;
    }) =>
      apiRequest<{ message: string }>("/preferences", {
        method: "PUT",
        body: data,
      }),
  },

  marketData: {
    candles: (symbol: string, timeframe: string = "1h", limit: number = 500) =>
      apiRequest<Array<{
        time: number;
        open: number;
        high: number;
        low: number;
        close: number;
        volume: number;
      }>>(`/market-data/candles/${encodeURIComponent(symbol)}?timeframe=${timeframe}&limit=${limit}`),
  },

  agentPerformance: {
    scores: (symbol: string, params?: { start?: string; end?: string; agents?: string; limit?: number }) => {
      const qs = new URLSearchParams();
      if (params?.start) qs.set("start", params.start);
      if (params?.end) qs.set("end", params.end);
      if (params?.agents) qs.set("agents", params.agents);
      if (params?.limit) qs.set("limit", String(params.limit));
      const query = qs.toString();
      return apiRequest<Array<{
        symbol: string;
        agent_name: string;
        score: number;
        confidence: number | null;
        metadata: Record<string, unknown> | null;
        recorded_at: string;
      }>>(`/agent-performance/scores/${encodeURIComponent(symbol)}${query ? `?${query}` : ""}`);
    },

    weights: (symbol: string) =>
      apiRequest<{
        weights: Record<string, number>;
        trackers: Record<string, { ewma: number | null; samples: number; last_updated: string | null }>;
      }>(`/agent-performance/weights/${encodeURIComponent(symbol)}`),

    attribution: (symbol: string, limit: number = 50) =>
      apiRequest<Array<{
        event_id: string;
        symbol: string;
        outcome: string;
        input_price: number | null;
        agents: Record<string, unknown> | null;
        created_at: string | null;
      }>>(`/agent-performance/attribution/${encodeURIComponent(symbol)}?limit=${limit}`),

    weightHistory: (symbol: string, params?: { agents?: string; limit?: number }) => {
      const qs = new URLSearchParams();
      if (params?.agents) qs.set("agents", params.agents);
      if (params?.limit) qs.set("limit", String(params.limit));
      const query = qs.toString();
      return apiRequest<Array<{
        symbol: string;
        agent_name: string;
        weight: number;
        ewma_accuracy: number;
        sample_count: number;
        recorded_at: string;
      }>>(`/agent-performance/weight-history/${encodeURIComponent(symbol)}${query ? `?${query}` : ""}`);
    },

    gateAnalytics: (symbol: string, limit: number = 500) =>
      apiRequest<{
        total_decisions: number;
        outcome_counts: Record<string, number>;
        gate_details: Record<string, { passed: number; blocked: number; reasons: Record<string, number> }>;
      }>(`/agent-performance/gate-analytics/${encodeURIComponent(symbol)}?limit=${limit}`),
  },

  agentConfig: {
    catalog: () =>
      apiRequest<Record<string, {
        label: string;
        type: string;
        params: Record<string, { type: string; default: unknown; description: string; [key: string]: unknown }>;
      }>>("/agent-config/agents"),

    getPipeline: (profileId: string) =>
      apiRequest<{
        nodes: Array<{ id: string; type: string; label: string; config?: Record<string, unknown>; position: { x: number; y: number } }>;
        edges: Array<{ id: string; source: string; target: string; condition?: string }>;
      }>(`/agent-config/${profileId}/pipeline`),

    savePipeline: (profileId: string, config: { nodes: unknown[]; edges: unknown[] }) =>
      apiRequest<{ status: string; profile_id: string }>(`/agent-config/${profileId}/pipeline`, {
        method: "PUT",
        body: config,
      }),

    resetPipeline: (profileId: string) =>
      apiRequest<{ status: string; profile_id: string }>(`/agent-config/${profileId}/pipeline/reset`, {
        method: "POST",
      }),

    overrideWeights: (profileId: string, weights: Record<string, number>) =>
      apiRequest<{ status: string; weights: Record<string, number> }>(`/agent-config/${profileId}/weights`, {
        method: "PUT",
        body: weights,
      }),

    clearWeightOverride: (profileId: string) =>
      apiRequest<{ status: string }>(`/agent-config/${profileId}/weights`, {
        method: "DELETE",
      }),
  },

  auth: {
    callback: (data: {
      email: string;
      name: string;
      image?: string;
      provider: string;
      provider_account_id: string;
    }) =>
      apiRequest<{
        access_token: string;
        refresh_token: string;
        user_id: string;
        display_name: string;
      }>("/auth/callback", {
        method: "POST",
        body: data,
      }),

    me: () =>
      apiRequest<{
        user_id: string;
        email: string;
        display_name: string;
        avatar_url?: string;
        provider: string;
      }>("/auth/me"),
  },
};

// ---- Backward-compatible legacy export ----
// Used by page.tsx and JSONRuleEditor.tsx from Phase 1

export const apiClient = {
  async fetch<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
    return apiRequest<T>(endpoint, options);
  },

  get<T>(endpoint: string) {
    return apiRequest<T>(endpoint, { method: "GET" });
  },

  post<T>(endpoint: string, body: unknown) {
    return apiRequest<T>(endpoint, { method: "POST", body });
  },

  put<T>(endpoint: string, body: unknown) {
    return apiRequest<T>(endpoint, { method: "PUT", body });
  },
};
