"use client";

import { useEffect, useState, useCallback } from "react";
import { api } from "@/lib/api/client";
import { AgentAccuracyTable } from "@/components/performance/AgentAccuracyTable";
import { GateBlockAnalytics } from "@/components/performance/GateBlockAnalytics";
import { WeightEvolutionChart } from "@/components/performance/WeightEvolutionChart";
import { TradeAttributionPanel } from "@/components/performance/TradeAttributionPanel";
import { Loader2, Activity } from "lucide-react";
import { motion } from "framer-motion";
import { pageEnter } from "@/lib/motion";

const SYMBOLS = ["BTC/USDT", "ETH/USDT"];

export default function PerformancePage() {
  const [symbol, setSymbol] = useState("BTC/USDT");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [weights, setWeights] = useState<{
    weights: Record<string, number>;
    trackers: Record<string, { ewma: number | null; samples: number; last_updated: string | null }>;
  } | null>(null);

  const [gateAnalytics, setGateAnalytics] = useState<{
    total_decisions: number;
    outcome_counts: Record<string, number>;
    gate_details: Record<string, { passed: number; blocked: number; reasons: Record<string, number> }>;
  } | null>(null);

  const [weightHistory, setWeightHistory] = useState<Array<{
    agent_name: string;
    weight: number;
    ewma_accuracy: number;
    sample_count: number;
    recorded_at: string;
  }>>([]);

  const [attribution, setAttribution] = useState<Array<{
    event_id: string;
    symbol: string;
    outcome: string;
    input_price: number | null;
    agents: Record<string, unknown> | null;
    created_at: string | null;
  }>>([]);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [w, ga, wh, attr] = await Promise.all([
        api.agentPerformance.weights(symbol),
        api.agentPerformance.gateAnalytics(symbol),
        api.agentPerformance.weightHistory(symbol, { agents: "ta,sentiment,debate", limit: 1000 }),
        api.agentPerformance.attribution(symbol, 100),
      ]);
      setWeights(w);
      setGateAnalytics(ga);
      setWeightHistory(wh);
      setAttribution(attr);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load performance data");
    } finally {
      setLoading(false);
    }
  }, [symbol]);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 60_000);
    return () => clearInterval(interval);
  }, [fetchData]);

  return (
    <motion.div
      className="p-6 space-y-6 max-w-[1600px] mx-auto"
      variants={pageEnter}
      initial="hidden"
      animate="show"
    >
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Activity className="w-5 h-5 text-violet-400" />
          <h1 className="text-lg font-semibold text-zinc-100">Agent Performance</h1>
        </div>
        <div className="flex gap-1">
          {SYMBOLS.map((s) => (
            <button
              key={s}
              onClick={() => setSymbol(s)}
              className={`px-3 py-1 rounded text-xs font-medium transition-colors ${
                symbol === s
                  ? "bg-violet-600 text-white"
                  : "bg-zinc-800 text-zinc-400 hover:bg-zinc-700"
              }`}
            >
              {s.replace("/USDT", "")}
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <div className="flex items-center justify-center h-64 bg-zinc-900/50 rounded-lg border border-zinc-800">
          <Loader2 className="w-6 h-6 text-violet-400 animate-spin" />
          <span className="ml-2 text-sm text-zinc-400">Loading performance data...</span>
        </div>
      ) : error ? (
        <div className="flex items-center justify-center h-64 bg-zinc-900/50 rounded-lg border border-zinc-800">
          <p className="text-sm text-red-400">{error}</p>
        </div>
      ) : (
        <>
          {/* Agent Accuracy Table */}
          <AgentAccuracyTable weights={weights} />

          {/* Charts row */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {/* Gate Block Analytics */}
            <GateBlockAnalytics data={gateAnalytics} />

            {/* Weight Evolution */}
            <WeightEvolutionChart data={weightHistory} />
          </div>

          {/* Trade Attribution */}
          <TradeAttributionPanel data={attribution} />
        </>
      )}
    </motion.div>
  );
}
