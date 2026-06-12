import { describe, it, expect } from "vitest";
import { parsePnlMessage } from "./client";

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
