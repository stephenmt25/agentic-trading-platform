/**
 * Typed API client for the Agentic Trading Platform backend.
 *
 * Auto-attaches the NextAuth.js session JWT as an Authorization header.
 * Redirects to /login on 401 responses.
 */

import { z } from "zod";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

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

  const response = await fetch(`${API_BASE_URL}${endpoint}`, config);

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
  success: z.boolean(),
  message: z.string(),
  permissions: z.array(z.string()),
});

const ProfileResponseSchema = z.object({
  profile_id: z.string(),
  name: z.string(),
  is_active: z.boolean(),
  rules_json: z.record(z.unknown()),
  allocation_pct: z.number(),
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
  success: boolean;
  message: string;
  permissions: string[];
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
  },

  exchangeKeys: {
    list: () =>
      validatedRequest(z.array(ExchangeKeyInfoSchema), "/exchange-keys"),

    store: (data: {
      exchange_name: string;
      api_key: string;
      api_secret: string;
      label?: string;
    }) =>
      apiRequest<StoreKeyResponse>("/exchange-keys", {
        method: "POST",
        body: data,
      }),

    test: (data: {
      api_key: string;
      api_secret: string;
      exchange_name: string;
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
