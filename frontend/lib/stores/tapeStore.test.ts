import { describe, it, expect, beforeEach } from "vitest";
import { useTapeStore } from "./tapeStore";

beforeEach(() => {
  useTapeStore.setState({ bySymbol: {} });
});

describe("tapeStore", () => {
  it("prepends new trades — newest first", () => {
    useTapeStore.getState().ingest({
      symbol: "BTC-PERP",
      exchange: "BINANCE",
      side: "ask",
      price: "42000.10",
      size: "0.5",
      timestampMs: 1,
      tradeId: "a",
    });
    useTapeStore.getState().ingest({
      symbol: "BTC-PERP",
      exchange: "BINANCE",
      side: "bid",
      price: "42000.05",
      size: "0.7",
      timestampMs: 2,
      tradeId: "b",
    });
    const trades = useTapeStore.getState().bySymbol["BTC-PERP"];
    expect(trades[0].tradeId).toBe("b");
    expect(trades[0].price).toBe(42000.05);
    expect(trades[1].tradeId).toBe("a");
  });

  it("caps the ring at 100 entries per symbol", () => {
    for (let i = 0; i < 150; i++) {
      useTapeStore.getState().ingest({
        symbol: "BTC-PERP",
        exchange: "BINANCE",
        side: i % 2 === 0 ? "bid" : "ask",
        price: 42000 + i,
        size: 0.1,
        timestampMs: i,
        tradeId: String(i),
      });
    }
    const trades = useTapeStore.getState().bySymbol["BTC-PERP"];
    expect(trades).toHaveLength(100);
    expect(trades[0].tradeId).toBe("149");
    expect(trades[99].tradeId).toBe("50");
  });

  it("isolates rings per symbol", () => {
    useTapeStore.getState().ingest({
      symbol: "BTC-PERP",
      exchange: "BINANCE",
      side: "bid",
      price: 1,
      size: 1,
      timestampMs: 1,
    });
    useTapeStore.getState().ingest({
      symbol: "ETH-PERP",
      exchange: "BINANCE",
      side: "ask",
      price: 2,
      size: 2,
      timestampMs: 1,
    });
    expect(useTapeStore.getState().bySymbol["BTC-PERP"]).toHaveLength(1);
    expect(useTapeStore.getState().bySymbol["ETH-PERP"]).toHaveLength(1);
    expect(useTapeStore.getState().bySymbol["ETH-PERP"][0].price).toBe(2);
  });
});
