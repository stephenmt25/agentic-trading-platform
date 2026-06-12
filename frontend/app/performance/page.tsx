"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import { queryKeys } from "@/lib/api/hooks";
import { AgentAccuracyTable } from "@/components/performance/AgentAccuracyTable";
import { GateBlockAnalytics } from "@/components/performance/GateBlockAnalytics";
import { WeightEvolutionChart } from "@/components/performance/WeightEvolutionChart";
import { TradeAttributionPanel } from "@/components/performance/TradeAttributionPanel";
import { Loader2, Activity } from "lucide-react";
import { motion } from "framer-motion";
import { pageEnter } from "@/lib/motion";

const SYMBOLS = ["BTC/USDT", "ETH/USDT"];

/**
 * The four reads land together (one loading state, one error state —
 * identical semantics to the pre-React-Query Promise.all) and share a
 * single query key so concurrent consumers collapse to one in-flight
 * request per symbol.
 */
async function fetchPerformance(symbol: string) {
  const [weights, gateAnalytics, weightHistory, attribution] = await Promise.all([
    api.agentPerformance.weights(symbol),
    api.agentPerformance.gateAnalytics(symbol),
    api.agentPerformance.weightHistory(symbol, { agents: "ta,sentiment,debate", limit: 1000 }),
    api.agentPerformance.attribution(symbol, 100),
  ]);
  return { weights, gateAnalytics, weightHistory, attribution };
}

export default function PerformancePage() {
  const [symbol, setSymbol] = useState("BTC/USDT");

  // FE-W2 pattern: the legacy 60s setInterval poller is now a React
  // Query refetchInterval — pauses while the tab is hidden, dedupes
  // across consumers, and stops when the page unmounts.
  const { data, isPending, error } = useQuery({
    queryKey: queryKeys.agentPerformance(symbol),
    queryFn: () => fetchPerformance(symbol),
    refetchInterval: 60_000,
  });

  return (
    /* /performance is an analytics surface — COOL mode, matching its
       siblings (/backtests, /agents, /hot/profiles cockpit). */
    <div data-mode="cool" className="min-h-full bg-bg-canvas text-fg">
      <motion.div
        className="p-6 space-y-6 max-w-[1600px] mx-auto"
        variants={pageEnter}
        initial="hidden"
        animate="show"
      >
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Activity className="w-5 h-5 text-accent-400" />
            <h1 className="text-lg font-semibold text-fg">Agent Performance</h1>
          </div>
          <div className="flex gap-1">
            {SYMBOLS.map((s) => (
              <button
                key={s}
                onClick={() => setSymbol(s)}
                className={`px-3 py-1 rounded text-xs font-medium transition-colors ${
                  symbol === s
                    ? "bg-accent-600 text-neutral-0"
                    : "bg-bg-raised text-fg-muted hover:bg-neutral-700"
                }`}
              >
                {s.replace("/USDT", "")}
              </button>
            ))}
          </div>
        </div>

        {error ? (
          /* Mirrors the legacy behavior: a failed fetch (first load OR a
             failed 60s repoll) surfaces the error panel in place of data. */
          <div className="flex items-center justify-center h-64 bg-bg-panel/50 rounded-lg border border-border-subtle">
            <p className="text-sm text-danger-500">
              {error instanceof Error ? error.message : "Failed to load performance data"}
            </p>
          </div>
        ) : isPending || !data ? (
          <div className="flex items-center justify-center h-64 bg-bg-panel/50 rounded-lg border border-border-subtle">
            <Loader2 className="w-6 h-6 text-accent-400 animate-spin will-change-transform" />
            <span className="ml-2 text-sm text-fg-muted">Loading performance data...</span>
          </div>
        ) : (
          <>
            {/* Agent Accuracy Table */}
            <AgentAccuracyTable weights={data.weights} />

            {/* Charts row */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              {/* Gate Block Analytics */}
              <GateBlockAnalytics data={data.gateAnalytics} />

              {/* Weight Evolution */}
              <WeightEvolutionChart data={data.weightHistory} />
            </div>

            {/* Trade Attribution */}
            <TradeAttributionPanel data={data.attribution} />
          </>
        )}
      </motion.div>
    </div>
  );
}
