import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { parsePnlMessage, wsClient } from "./client";
import { useAuthStore } from "../stores/authStore";
import { clearSessionTokenCache } from "../api/client";

// Real wire shape: PnlUpdateEvent with Decimal fields str-encoded
// (registry row 54), forwarded verbatim by the gateway.
const wireMessage = {
  event_id: "00000000-0000-4000-8000-000000000001",
  event_type: "PNL_UPDATE",
  timestamp_us: 1_700_000_000_000_000,
  source_service: "pnl",
  schema_version: 1,
  profile_id: "prof-1",
  position_id: "pos-1",
  symbol: "BTC/USDT",
  gross_pnl: "125.50",
  net_pnl: "122.25",
  fees: "3.25",
  net_pre_tax: "122.25",
  net_post_tax: "103.91",
  tax_estimate: "18.34",
  pct_return: "0.0207",
};

describe("parsePnlMessage", () => {
  it("parses str-encoded Decimals into numbers", () => {
    const snapshot = parsePnlMessage(wireMessage);
    expect(snapshot).not.toBeNull();
    expect(snapshot!).toMatchObject({
      position_id: "pos-1",
      profile_id: "prof-1",
      symbol: "BTC/USDT",
      gross_pnl: 125.5,
      fees: 3.25,
      net_pre_tax: 122.25,
      net_post_tax: 103.91,
      tax_estimate: 18.34,
      pct_return: 0.0207,
      timestamp_us: 1_700_000_000_000_000,
    });
  });

  it("accepts numeric-typed fields too (legacy payloads)", () => {
    const snapshot = parsePnlMessage({
      ...wireMessage,
      net_post_tax: 103.91,
      pct_return: 0.0207,
    });
    expect(snapshot!.net_post_tax).toBe(103.91);
    expect(snapshot!.pct_return).toBe(0.0207);
  });

  it("maps missing or unparseable numeric fields to null", () => {
    const snapshot = parsePnlMessage({
      ...wireMessage,
      fees: undefined,
      tax_estimate: "not-a-number",
      net_pre_tax: "",
      gross_pnl: null,
    });
    expect(snapshot).not.toBeNull();
    expect(snapshot!.fees).toBeNull();
    expect(snapshot!.tax_estimate).toBeNull();
    expect(snapshot!.net_pre_tax).toBeNull();
    expect(snapshot!.gross_pnl).toBeNull();
    // Untouched fields still parse
    expect(snapshot!.net_post_tax).toBe(103.91);
  });

  it("drops messages without a position_id (events are per-position)", () => {
    const { position_id: _omitted, ...withoutPositionId } = wireMessage;
    expect(parsePnlMessage(withoutPositionId)).toBeNull();
    expect(parsePnlMessage(null)).toBeNull();
    expect(parsePnlMessage("not-an-object")).toBeNull();
  });

  it("falls back to a wall-clock timestamp_us when missing", () => {
    const before = Date.now() * 1000;
    const snapshot = parsePnlMessage({ ...wireMessage, timestamp_us: undefined });
    const after = Date.now() * 1000;
    expect(snapshot!.timestamp_us).toBeGreaterThanOrEqual(before);
    expect(snapshot!.timestamp_us).toBeLessThanOrEqual(after);
  });
});

// ── Token refresh on (re)connect — registry row 31 remainder ─────────────
// Every connect must resolve a session-fresh token instead of reusing the
// authStore JWT captured at an earlier time (a long-idle tab's store JWT
// can be expired while the NextAuth session endpoint re-mints a valid one).

class FakeWebSocket {
  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSING = 2;
  static CLOSED = 3;
  static instances: FakeWebSocket[] = [];
  url: string;
  readyState = FakeWebSocket.CONNECTING;
  onopen: (() => void) | null = null;
  onmessage: ((e: { data: unknown }) => void) | null = null;
  onerror: (() => void) | null = null;
  onclose: (() => void) | null = null;
  constructor(url: string) {
    this.url = url;
    FakeWebSocket.instances.push(this);
  }
  close() {
    this.readyState = FakeWebSocket.CLOSED;
  }
  send() {}
}

describe("wsClient.connect — session-fresh token per (re)connect", () => {
  beforeEach(() => {
    FakeWebSocket.instances = [];
    vi.stubGlobal("WebSocket", FakeWebSocket);
    clearSessionTokenCache();
    useAuthStore.getState().setSession("stale-store-jwt", "user@test");
  });

  afterEach(() => {
    wsClient.disconnect();
    clearSessionTokenCache();
    useAuthStore.getState().logout();
    vi.unstubAllGlobals();
  });

  it("puts the session-endpoint token in the WS URL, not the store JWT", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        json: async () => ({ accessToken: "fresh-session-token" }),
      }))
    );

    wsClient.connect();
    await vi.waitFor(() => {
      expect(FakeWebSocket.instances.length).toBe(1);
    });

    const url = FakeWebSocket.instances[0].url;
    expect(url).toContain("token=fresh-session-token");
    expect(url).not.toContain("stale-store-jwt");
  });

  it("falls back to the store JWT when the session endpoint is unreachable", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        throw new Error("offline");
      })
    );

    wsClient.connect();
    await vi.waitFor(() => {
      expect(FakeWebSocket.instances.length).toBe(1);
    });

    expect(FakeWebSocket.instances[0].url).toContain("token=stale-store-jwt");
  });

  it("does not open a second socket while a connect is already in flight", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        json: async () => ({ accessToken: "fresh-session-token" }),
      }))
    );

    wsClient.connect();
    wsClient.connect(); // second call during the async token resolution
    await vi.waitFor(() => {
      expect(FakeWebSocket.instances.length).toBeGreaterThanOrEqual(1);
    });
    // Give any stray second connect a chance to (incorrectly) land.
    await new Promise((r) => setTimeout(r, 10));
    expect(FakeWebSocket.instances.length).toBe(1);
  });
});
