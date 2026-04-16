"use client";

import { useAnalysisStore } from "@/lib/stores/analysisStore";

const SYMBOLS = ["BTC/USDT", "ETH/USDT"];

export function SymbolSelector() {
  const symbol = useAnalysisStore((s) => s.symbol);
  const setSymbol = useAnalysisStore((s) => s.setSymbol);

  return (
    <div className="flex gap-1">
      {SYMBOLS.map((s) => (
        <button
          key={s}
          onClick={() => setSymbol(s)}
          className={`px-3 py-1 rounded text-xs font-medium transition-colors ${
            symbol === s
              ? "bg-blue-600 text-white"
              : "bg-zinc-800 text-zinc-400 hover:bg-zinc-700 hover:text-zinc-300"
          }`}
        >
          {s.replace("/USDT", "")}
        </button>
      ))}
    </div>
  );
}
