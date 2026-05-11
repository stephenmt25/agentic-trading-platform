"use client";

import { create } from "zustand";

export type TradingMode = "PAPER" | "TESTNET" | "LIVE";

interface TradingModeStore {
  mode: TradingMode | null;
  setMode: (m: TradingMode | null) => void;
}

/**
 * Trading mode (PAPER / TESTNET / LIVE), mirrored from
 * GET /paper-trading/mode (api.paperTrading.mode). Read by the chrome
 * StatusPills and HotChrome pills row so users always see whether the
 * platform is talking to real money — misreading the mode is a real-money
 * risk class. Fetched once per session by ChromeBar; refreshed when the
 * backend reconnects.
 */
export const useTradingModeStore = create<TradingModeStore>((set) => ({
  mode: null,
  setMode: (m) => set({ mode: m }),
}));
