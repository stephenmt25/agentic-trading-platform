"use client";

import { create } from "zustand";

export interface OrderBookLevel {
  price: number;
  size: number;
}

export interface OrderBookSnapshot {
  symbol: string;
  exchange: string;
  bids: OrderBookLevel[]; // descending price
  asks: OrderBookLevel[]; // ascending price
  /** ms epoch — last update time as reported by the exchange. */
  timestampMs: number;
}

interface OrderBookStore {
  bySymbol: Record<string, OrderBookSnapshot>;
  /**
   * Replace the snapshot for a symbol. Bids/asks are passed as
   * tuple-encoded strings off the wire (Decimal → str via msgpack default).
   */
  ingest: (
    symbol: string,
    exchange: string,
    bids: Array<[string | number, string | number]>,
    asks: Array<[string | number, string | number]>,
    timestampMs: number
  ) => void;
}

const toNumber = (v: string | number): number =>
  typeof v === "number" ? v : parseFloat(v);

/**
 * Latest top-N orderbook snapshot per symbol. Backed by the
 * `pubsub:orderbook` Redis channel produced by services/ingestion via
 * CCXT watch_order_book. The frontend filters by symbol — the backend
 * channel is global to keep the WS subscription list bounded.
 *
 * Snapshots replace wholesale (full top-N each emission) — there is no
 * incremental diff path, intentional given Binance's debounce and the
 * channel's ~10Hz emission rate.
 */
export const useOrderBookStore = create<OrderBookStore>((set) => ({
  bySymbol: {},
  ingest: (symbol, exchange, bids, asks, timestampMs) =>
    set((state) => ({
      bySymbol: {
        ...state.bySymbol,
        [symbol]: {
          symbol,
          exchange,
          bids: bids.map(([p, s]) => ({ price: toNumber(p), size: toNumber(s) })),
          asks: asks.map(([p, s]) => ({ price: toNumber(p), size: toNumber(s) })),
          timestampMs,
        },
      },
    })),
}));
