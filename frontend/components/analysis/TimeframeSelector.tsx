"use client";

import { useAnalysisStore, type Timeframe } from "@/lib/stores/analysisStore";

const TIMEFRAMES: { value: Timeframe; label: string }[] = [
  { value: "1m", label: "1m" },
  { value: "5m", label: "5m" },
  { value: "15m", label: "15m" },
  { value: "1h", label: "1H" },
  { value: "4h", label: "4H" },
  { value: "1d", label: "1D" },
];

export function TimeframeSelector() {
  const timeframe = useAnalysisStore((s) => s.timeframe);
  const setTimeframe = useAnalysisStore((s) => s.setTimeframe);

  return (
    <div className="flex gap-1">
      {TIMEFRAMES.map((tf) => (
        <button
          key={tf.value}
          onClick={() => setTimeframe(tf.value)}
          className={`px-2.5 py-1 rounded text-xs font-medium transition-colors ${
            timeframe === tf.value
              ? "bg-blue-600 text-white"
              : "bg-zinc-800 text-zinc-400 hover:bg-zinc-700 hover:text-zinc-300"
          }`}
        >
          {tf.label}
        </button>
      ))}
    </div>
  );
}
