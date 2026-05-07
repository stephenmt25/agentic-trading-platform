"use client";

import { useEffect, useState, useCallback } from "react";
import { api } from "@/lib/api/client";
import { GateBlockAnalytics } from "@/components/performance/GateBlockAnalytics";
import { WeightEvolutionChart } from "@/components/performance/WeightEvolutionChart";
import { TradeForensicsCard } from "@/components/performance/TradeForensicsCard";
import { Loader2 } from "lucide-react";

const SYMBOLS = ["BTC/USDT", "ETH/USDT"];

interface PerformanceContentProps {
  profileId?: string | null;
}

export default function PerformanceContent({ profileId }: PerformanceContentProps = {}) {
  const [symbol, setSymbol] = useState("BTC/USDT");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [gateAnalytics, setGateAnalytics] = useState<any>(null);
  const [weightHistory, setWeightHistory] = useState<any[]>([]);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [ga, wh] = await Promise.all([
        api.agentPerformance.gateAnalytics(symbol, profileId ? { profileId } : undefined),
        api.agentPerformance.weightHistory(symbol, { agents: "ta,sentiment,debate", limit: 1000 }),
      ]);
      setGateAnalytics(ga);
      setWeightHistory(wh);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load performance data");
    } finally {
      setLoading(false);
    }
  }, [symbol, profileId]);

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
          <p className="text-[11px] text-muted-foreground">
            Current agent weights live in the Trade page · Analysis section. This drawer focuses on
            gate efficacy, weight evolution over time, and Trade Forensics — open the card below to
            slice closed and approved trades, then open the raw tables on demand.
          </p>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <GateBlockAnalytics data={gateAnalytics} />
            <WeightEvolutionChart data={weightHistory} />
          </div>
          <TradeForensicsCard symbol={symbol} profileId={profileId ?? null} />
        </>
      )}
    </div>
  );
}
