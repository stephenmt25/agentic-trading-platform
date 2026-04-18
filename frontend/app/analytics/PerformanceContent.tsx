"use client";

import { useEffect, useState, useCallback } from "react";
import { api } from "@/lib/api/client";
import { AgentAccuracyTable } from "@/components/performance/AgentAccuracyTable";
import { GateBlockAnalytics } from "@/components/performance/GateBlockAnalytics";
import { WeightEvolutionChart } from "@/components/performance/WeightEvolutionChart";
import { TradeAttributionPanel } from "@/components/performance/TradeAttributionPanel";
import { InfoTooltip } from "@/components/ui/InfoTooltip";
import { Loader2 } from "lucide-react";

const SYMBOLS = ["BTC/USDT", "ETH/USDT"];

export default function PerformanceContent() {
  const [symbol, setSymbol] = useState("BTC/USDT");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [weights, setWeights] = useState<any>(null);
  const [gateAnalytics, setGateAnalytics] = useState<any>(null);
  const [weightHistory, setWeightHistory] = useState<any[]>([]);
  const [attribution, setAttribution] = useState<any[]>([]);

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
    <div className="space-y-6">
      {/* Symbol selector */}
      <div className="flex justify-end gap-1">
        {SYMBOLS.map((s) => (
          <button
            key={s}
            onClick={() => setSymbol(s)}
            className={`px-3 py-1 rounded text-xs font-medium transition-colors ${
              symbol === s ? "bg-primary text-primary-foreground" : "bg-accent text-muted-foreground hover:text-foreground"
            }`}
          >
            {s.replace("/USDT", "")}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="flex items-center justify-center h-64 border border-border rounded-md">
          <Loader2 className="w-5 h-5 animate-spin text-muted-foreground" />
          <span className="ml-2 text-sm text-muted-foreground">Loading performance data...</span>
        </div>
      ) : error ? (
        <div className="flex items-center justify-center h-64 border border-border rounded-md">
          <p className="text-sm text-red-500">{error}</p>
        </div>
      ) : (
        <>
          <AgentAccuracyTable weights={weights} />
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <GateBlockAnalytics data={gateAnalytics} />
            <WeightEvolutionChart data={weightHistory} />
          </div>
          <TradeAttributionPanel data={attribution} />
        </>
      )}
    </div>
  );
}
