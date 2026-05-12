"use client";

import { create } from "zustand";

export interface TradePrint {
  symbol: string;
  exchange: string;
  side: "bid" | "ask";
  price: number;
  size: number;
  timestampMs: number;
  tradeId?: string | null;
}

const RING_CAP = 100;

interface TapeStore {
  /** Ring buffer per symbol — newest first, capped at RING_CAP. */
  bySymbol: Record<string, TradePrint[]>;
  ingest: (trade: {
    symbol: string;
    exchange: string;
    side: "bid" | "ask";
    price: string | number;
    size: string | number;
    timestampMs: number;
    tradeId?: string | null;
  }) => void;
}

const toNumber = (v: string | number): number =>
  typeof v === "number" ? v : parseFloat(v);

/**
 * Per-symbol tape feed. Backed by the `pubsub:trades` Redis channel
 * produced by services/ingestion via CCXT watch_trades. Newest trade
 * is index 0 so the surface can render with `slice(0, n)` directly.
 *
 * The ring is per-symbol so switching symbols on /hot doesn't drop the
 * background tape state for other symbols (cheap to keep — RING_CAP × 6
 * fields × ~3 symbols = nothing).
 */
export const useTapeStore = create<TapeStore>((set) => ({
  bySymbol: {},
  ingest: (trade) =>
    set((state) => {
      const print: TradePrint = {
        symbol: trade.symbol,
        exchange: trade.exchange,
        side: trade.side,
        price: toNumber(trade.price),
        size: toNumber(trade.size),
        timestampMs: trade.timestampMs,
        tradeId: trade.tradeId ?? null,
      };
      const prev = state.bySymbol[trade.symbol] ?? [];
      const next = [print, ...prev].slice(0, RING_CAP);
      return {
        bySymbol: { ...state.bySymbol, [trade.symbol]: next },
      };
    }),
}));
