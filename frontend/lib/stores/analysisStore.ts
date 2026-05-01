import { create } from "zustand";

export type Timeframe = "1m" | "5m" | "15m" | "1h";
export type AgentOverlay = "ta" | "sentiment" | "debate" | "regime_hmm";

export interface VisibleRange {
  from: number;
  to: number;
}

export interface PinnedDecision {
  eventId: string;
  time: number; // epoch seconds — decision created_at
  symbol: string;
  outcome: string; // APPROVED | BLOCKED_*
  direction: "BUY" | "SELL";
}

interface AnalysisState {
  symbol: string;
  timeframe: Timeframe;
  visibleOverlays: AgentOverlay[];
  showIndicators: boolean;
  showTradeMarkers: boolean;
  showRegimeBands: boolean;
  hoveredTime: number | null;
  hoverSource: "price" | "score" | null;
  visibleRange: VisibleRange | null;
  pinnedDecision: PinnedDecision | null;
  setSymbol: (s: string) => void;
  setTimeframe: (tf: Timeframe) => void;
  toggleOverlay: (agent: AgentOverlay) => void;
  setShowIndicators: (v: boolean) => void;
  setShowTradeMarkers: (v: boolean) => void;
  setShowRegimeBands: (v: boolean) => void;
  setHoveredTime: (t: number | null, source: "price" | "score" | null) => void;
  setVisibleRange: (r: VisibleRange | null) => void;
  pinDecision: (p: PinnedDecision) => void;
  clearPinnedDecision: () => void;
}

export const useAnalysisStore = create<AnalysisState>((set) => ({
  symbol: "BTC/USDT",
  timeframe: "1h",
  visibleOverlays: ["ta", "sentiment", "debate"],
  showIndicators: true,
  showTradeMarkers: true,
  showRegimeBands: true,
  hoveredTime: null,
  hoverSource: null,
  visibleRange: null,
  pinnedDecision: null,

  setSymbol: (symbol) => set({ symbol }),
  setTimeframe: (timeframe) => set({ timeframe }),
  toggleOverlay: (agent) =>
    set((state) => ({
      visibleOverlays: state.visibleOverlays.includes(agent)
        ? state.visibleOverlays.filter((a) => a !== agent)
        : [...state.visibleOverlays, agent],
    })),
  setShowIndicators: (v) => set({ showIndicators: v }),
  setShowTradeMarkers: (v) => set({ showTradeMarkers: v }),
  setShowRegimeBands: (v) => set({ showRegimeBands: v }),
  setHoveredTime: (hoveredTime, hoverSource) => set({ hoveredTime, hoverSource }),
  setVisibleRange: (visibleRange) => set({ visibleRange }),
  // Pinning a decision auto-switches the chart to that decision's symbol on
  // the 1m timeframe (which is what the strategy evaluates on, so the marker
  // lands on the correct candle).
  pinDecision: (p) => set({ pinnedDecision: p, symbol: p.symbol, timeframe: "1m" }),
  clearPinnedDecision: () => set({ pinnedDecision: null }),
}));
