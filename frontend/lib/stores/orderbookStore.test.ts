import { describe, it, expect, beforeEach } from "vitest";
import { useOrderBookStore } from "./orderbookStore";

beforeEach(() => {
  useOrderBookStore.setState({ bySymbol: {} });
});

describe("orderbookStore", () => {
  it("ingests string-encoded levels (Decimal-on-the-wire) as numbers", () => {
    useOrderBookStore.getState().ingest(
      "BTC-PERP",
      "BINANCE",
      [
        ["42000.10", "0.500"],
        ["42000.05", "1.200"],
      ],
      [
        ["42000.20", "0.300"],
        ["42000.25", "0.800"],
      ],
      1_700_000_000_000
    );
    const snap = useOrderBookStore.getState().bySymbol["BTC-PERP"];
    expect(snap).toBeDefined();
    expect(snap.exchange).toBe("BINANCE");
    expect(snap.bids).toEqual([
      { price: 42000.1, size: 0.5 },
      { price: 42000.05, size: 1.2 },
    ]);
    expect(snap.asks[0]).toEqual({ price: 42000.2, size: 0.3 });
    expect(snap.timestampMs).toBe(1_700_000_000_000);
  });

  it("replaces snapshots wholesale per symbol — no merge", () => {
    useOrderBookStore.getState().ingest(
      "BTC-PERP",
      "BINANCE",
      [["1", "1"]],
      [["2", "1"]],
      1
    );
    useOrderBookStore.getState().ingest(
      "BTC-PERP",
      "BINANCE",
      [["3", "2"]],
      [["4", "2"]],
      2
    );
    const snap = useOrderBookStore.getState().bySymbol["BTC-PERP"];
    expect(snap.bids).toEqual([{ price: 3, size: 2 }]);
    expect(snap.asks).toEqual([{ price: 4, size: 2 }]);
    expect(snap.timestampMs).toBe(2);
  });

  it("keeps multiple symbols independent", () => {
    useOrderBookStore.getState().ingest("BTC-PERP", "BINANCE", [["1", "1"]], [["2", "1"]], 1);
    useOrderBookStore.getState().ingest("ETH-PERP", "BINANCE", [["10", "5"]], [["11", "5"]], 1);
    const all = useOrderBookStore.getState().bySymbol;
    expect(Object.keys(all).sort()).toEqual(["BTC-PERP", "ETH-PERP"]);
  });
});
