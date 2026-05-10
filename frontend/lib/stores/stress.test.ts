import { describe, it, expect, beforeEach } from "vitest";
import { useOrderBookStore } from "./orderbookStore";
import { useTapeStore } from "./tapeStore";

/**
 * Phase 7 / Phase 8.4 perf budget — store ingest path.
 *
 * The targets in the redesign exec plan: no frame drop on /hot OrderBook
 * at 100 updates/s. The store layer has to keep up well below 16ms/frame
 * so rendering can have the rest of the budget. We assert ingest stays
 * under generous bounds; the test will start failing loudly if a future
 * change re-introduces a per-update copy of the entire ring or similar.
 */

beforeEach(() => {
  useOrderBookStore.setState({ bySymbol: {} });
  useTapeStore.setState({ bySymbol: {} });
});

const makeBook = (mid: number, depth = 25): {
  bids: Array<[string, string]>;
  asks: Array<[string, string]>;
} => {
  const bids: Array<[string, string]> = [];
  const asks: Array<[string, string]> = [];
  for (let i = 0; i < depth; i++) {
    bids.push([(mid - 0.01 * (i + 1)).toFixed(2), (0.5 + i * 0.1).toFixed(4)]);
    asks.push([(mid + 0.01 * (i + 1)).toFixed(2), (0.5 + i * 0.1).toFixed(4)]);
  }
  return { bids, asks };
};

describe("store ingest stress", () => {
  it("orderbook ingests 1000 snapshots in well under one frame each", () => {
    const ingest = useOrderBookStore.getState().ingest;
    const start = performance.now();
    for (let i = 0; i < 1000; i++) {
      const { bids, asks } = makeBook(80000 + (i % 50));
      ingest("BTC-USDT", "BINANCE", bids, asks, 1_700_000_000_000 + i);
    }
    const total = performance.now() - start;
    const avgMs = total / 1000;
    // 1ms per snapshot is a loose budget — 100 updates/s = 100ms/s for
    // ingest alone, leaves >900ms/s for everything else. Tighten if it
    // ever drifts up.
    expect(avgMs).toBeLessThan(1);
    expect(useOrderBookStore.getState().bySymbol["BTC-USDT"].bids.length).toBe(25);
  });

  it("tape ingest at 100Hz stays under 0.5ms per event", () => {
    const ingest = useTapeStore.getState().ingest;
    const start = performance.now();
    for (let i = 0; i < 1000; i++) {
      ingest({
        symbol: "BTC-USDT",
        exchange: "BINANCE",
        side: i % 2 === 0 ? "bid" : "ask",
        price: 80000 + (i % 100),
        size: 0.001,
        timestampMs: 1_700_000_000_000 + i,
        tradeId: String(i),
      });
    }
    const avgMs = (performance.now() - start) / 1000;
    expect(avgMs).toBeLessThan(0.5);
    // Ring cap at 100 entries.
    expect(useTapeStore.getState().bySymbol["BTC-USDT"]).toHaveLength(100);
  });

  it("orderbook selector returns stable identity for unrelated symbol updates", () => {
    const ingest = useOrderBookStore.getState().ingest;
    ingest("BTC-USDT", "BINANCE", [["80000", "1"]], [["80001", "1"]], 1);
    const before = useOrderBookStore.getState().bySymbol["BTC-USDT"];
    // Update a different symbol — should NOT touch BTC's snapshot identity.
    ingest("ETH-USDT", "BINANCE", [["2300", "1"]], [["2301", "1"]], 2);
    const after = useOrderBookStore.getState().bySymbol["BTC-USDT"];
    expect(after).toBe(before);
  });

  it("tape selector returns stable identity for unrelated symbol updates", () => {
    const ingest = useTapeStore.getState().ingest;
    ingest({
      symbol: "BTC-USDT",
      exchange: "BINANCE",
      side: "bid",
      price: 80000,
      size: 0.001,
      timestampMs: 1,
    });
    const before = useTapeStore.getState().bySymbol["BTC-USDT"];
    ingest({
      symbol: "ETH-USDT",
      exchange: "BINANCE",
      side: "ask",
      price: 2300,
      size: 0.05,
      timestampMs: 2,
    });
    const after = useTapeStore.getState().bySymbol["BTC-USDT"];
    expect(after).toBe(before);
  });
});
