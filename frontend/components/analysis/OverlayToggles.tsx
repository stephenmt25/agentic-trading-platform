"use client";

import { useAnalysisStore, type AgentOverlay } from "@/lib/stores/analysisStore";

const OVERLAYS: { key: AgentOverlay; label: string; color: string }[] = [
  { key: "ta", label: "TA", color: "bg-blue-500" },
  { key: "sentiment", label: "Sent", color: "bg-violet-500" },
  { key: "debate", label: "Debate", color: "bg-amber-500" },
  { key: "regime_hmm", label: "Regime", color: "bg-pink-500" },
];

export function OverlayToggles() {
  const visibleOverlays = useAnalysisStore((s) => s.visibleOverlays);
  const toggleOverlay = useAnalysisStore((s) => s.toggleOverlay);
  const showTradeMarkers = useAnalysisStore((s) => s.showTradeMarkers);
  const setShowTradeMarkers = useAnalysisStore((s) => s.setShowTradeMarkers);
  const showRegimeBands = useAnalysisStore((s) => s.showRegimeBands);
  const setShowRegimeBands = useAnalysisStore((s) => s.setShowRegimeBands);

  return (
    <div className="flex gap-1 items-center">
      <span className="text-xs text-zinc-500 mr-1">Overlays:</span>
      {OVERLAYS.map((o) => {
        const active = visibleOverlays.includes(o.key);
        return (
          <button
            key={o.key}
            onClick={() => toggleOverlay(o.key)}
            className={`px-2 py-0.5 rounded text-xs font-medium transition-colors flex items-center gap-1 ${
              active
                ? "bg-zinc-700 text-white"
                : "bg-zinc-800/50 text-zinc-500 hover:text-zinc-400"
            }`}
          >
            <span className={`w-1.5 h-1.5 rounded-full ${active ? o.color : "bg-zinc-600"}`} />
            {o.label}
          </button>
        );
      })}
      <span className="w-px h-4 bg-zinc-700 mx-1" />
      <button
        onClick={() => setShowTradeMarkers(!showTradeMarkers)}
        className={`px-2 py-0.5 rounded text-xs font-medium transition-colors ${
          showTradeMarkers
            ? "bg-zinc-700 text-white"
            : "bg-zinc-800/50 text-zinc-500 hover:text-zinc-400"
        }`}
      >
        Trades
      </button>
      <button
        onClick={() => setShowRegimeBands(!showRegimeBands)}
        className={`px-2 py-0.5 rounded text-xs font-medium transition-colors ${
          showRegimeBands
            ? "bg-zinc-700 text-white"
            : "bg-zinc-800/50 text-zinc-500 hover:text-zinc-400"
        }`}
      >
        Regime
      </button>
    </div>
  );
}
