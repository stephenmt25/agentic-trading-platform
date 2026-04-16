"use client";

import { useEffect, useState, useCallback } from "react";
import { api } from "@/lib/api/client";
import { useAnalysisStore } from "@/lib/stores/analysisStore";
import { PriceChart } from "@/components/analysis/PriceChart";
import { AgentScoreOverlay } from "@/components/analysis/AgentScoreOverlay";
import { TimeframeSelector } from "@/components/analysis/TimeframeSelector";
import { SymbolSelector } from "@/components/analysis/SymbolSelector";
import { OverlayToggles } from "@/components/analysis/OverlayToggles";
import { Loader2, BarChart3 } from "lucide-react";
import { motion } from "framer-motion";
import { pageEnter } from "@/lib/motion";

interface CandleData {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

interface ScoreDataPoint {
  symbol: string;
  agent_name: string;
  score: number;
  confidence: number | null;
  recorded_at: string;
}

interface WeightData {
  weights: Record<string, number>;
  trackers: Record<string, { ewma: number | null; samples: number; last_updated: string | null }>;
}

export default function AnalysisPage() {
  const symbol = useAnalysisStore((s) => s.symbol);
  const timeframe = useAnalysisStore((s) => s.timeframe);
  const visibleOverlays = useAnalysisStore((s) => s.visibleOverlays);

  const [candles, setCandles] = useState<CandleData[]>([]);
  const [scores, setScores] = useState<ScoreDataPoint[]>([]);
  const [weights, setWeights] = useState<WeightData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [candleData, scoreData, weightData] = await Promise.all([
        api.marketData.candles(symbol, timeframe, 500),
        api.agentPerformance.scores(symbol, {
          agents: "ta,sentiment,debate,regime_hmm",
          limit: 2000,
        }),
        api.agentPerformance.weights(symbol),
      ]);
      setCandles(candleData);
      setScores(scoreData);
      setWeights(weightData);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load data");
    } finally {
      setLoading(false);
    }
  }, [symbol, timeframe]);

  useEffect(() => {
    fetchData();
    // Auto-refresh every 60 seconds
    const interval = setInterval(fetchData, 60_000);
    return () => clearInterval(interval);
  }, [fetchData]);

  return (
    <motion.div
      className="p-6 space-y-4 max-w-[1600px] mx-auto"
      variants={pageEnter}
      initial="hidden"
      animate="show"
    >
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-3">
          <BarChart3 className="w-5 h-5 text-blue-400" />
          <h1 className="text-lg font-semibold text-zinc-100">Analysis</h1>
        </div>
        <div className="flex items-center gap-3 flex-wrap">
          <SymbolSelector />
          <span className="w-px h-5 bg-zinc-700" />
          <TimeframeSelector />
        </div>
      </div>

      {/* Overlay controls */}
      <OverlayToggles />

      {/* Main chart area */}
      {loading ? (
        <div className="flex items-center justify-center h-[400px] bg-zinc-900/50 rounded-lg border border-zinc-800">
          <Loader2 className="w-6 h-6 text-blue-400 animate-spin" />
          <span className="ml-2 text-sm text-zinc-400">Loading chart data...</span>
        </div>
      ) : error ? (
        <div className="flex items-center justify-center h-[400px] bg-zinc-900/50 rounded-lg border border-zinc-800">
          <p className="text-sm text-red-400">{error}</p>
        </div>
      ) : (
        <div className="space-y-1">
          {/* Candlestick chart */}
          <div className="bg-zinc-900/50 rounded-lg border border-zinc-800 p-2">
            <PriceChart
              data={candles}
              height={420}
            />
          </div>

          {/* Agent score overlay */}
          {visibleOverlays.length > 0 && (
            <div className="bg-zinc-900/50 rounded-lg border border-zinc-800 p-2">
              <div className="flex items-center justify-between mb-1 px-1">
                <span className="text-xs text-zinc-500 font-medium">Agent Scores</span>
                <div className="flex gap-3">
                  {visibleOverlays.map((agent) => {
                    const colors: Record<string, string> = {
                      ta: "text-blue-400",
                      sentiment: "text-violet-400",
                      debate: "text-amber-400",
                      regime_hmm: "text-pink-400",
                    };
                    return (
                      <span key={agent} className={`text-xs ${colors[agent]}`}>
                        {agent.toUpperCase()}
                      </span>
                    );
                  })}
                </div>
              </div>
              <AgentScoreOverlay
                data={scores}
                visibleAgents={visibleOverlays}
                height={160}
              />
            </div>
          )}
        </div>
      )}

      {/* Agent weights summary */}
      {weights && (
        <div className="bg-zinc-900/50 rounded-lg border border-zinc-800 p-4">
          <h3 className="text-xs font-medium text-zinc-500 mb-3">
            Current Agent Weights ({symbol})
          </h3>
          <div className="grid grid-cols-3 gap-4">
            {Object.entries(weights.trackers).map(([agent, tracker]) => {
              const weight = weights.weights[agent];
              const defaults: Record<string, number> = {
                ta: 0.2,
                sentiment: 0.15,
                debate: 0.25,
              };
              const defaultWeight = defaults[agent] ?? 0;
              const delta = weight != null ? weight - defaultWeight : 0;
              return (
                <div key={agent} className="space-y-1">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-medium text-zinc-300 uppercase">
                      {agent}
                    </span>
                    <span className="text-xs text-zinc-500">
                      {tracker.samples} samples
                    </span>
                  </div>
                  <div className="flex items-baseline gap-2">
                    <span className="text-lg font-mono text-zinc-100">
                      {weight != null ? weight.toFixed(3) : "—"}
                    </span>
                    {delta !== 0 && (
                      <span
                        className={`text-xs font-mono ${
                          delta > 0 ? "text-green-400" : "text-red-400"
                        }`}
                      >
                        {delta > 0 ? "+" : ""}
                        {delta.toFixed(3)}
                      </span>
                    )}
                  </div>
                  <div className="w-full bg-zinc-800 rounded-full h-1">
                    <div
                      className="bg-blue-500 h-1 rounded-full transition-all"
                      style={{
                        width: `${Math.min(100, (tracker.ewma ?? 0) * 100)}%`,
                      }}
                    />
                  </div>
                  <span className="text-[10px] text-zinc-500">
                    EWMA: {tracker.ewma != null ? (tracker.ewma * 100).toFixed(1) + "%" : "—"}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </motion.div>
  );
}
