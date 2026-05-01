"use client";

import { useEffect, useState, useCallback } from "react";
import { api } from "@/lib/api/client";
import { useAnalysisStore } from "@/lib/stores/analysisStore";
import { PriceChart } from "@/components/analysis/PriceChart";
import { AgentScoreOverlay } from "@/components/analysis/AgentScoreOverlay";
import { TimeframeSelector } from "@/components/analysis/TimeframeSelector";
import { SymbolSelector } from "@/components/analysis/SymbolSelector";
import { OverlayToggles } from "@/components/analysis/OverlayToggles";
import { InfoTooltip } from "@/components/ui/InfoTooltip";
import { Loader2 } from "lucide-react";

interface CandleData {
  time: number; open: number; high: number; low: number; close: number; volume: number;
}
interface ScoreDataPoint {
  symbol: string; agent_name: string; score: number; confidence: number | null; recorded_at: string;
}
interface WeightData {
  weights: Record<string, number>;
  trackers: Record<string, { ewma: number | null; samples: number; last_updated: string | null }>;
}

// An agent is "hydrated" if it has at least one recent score that's a real, non-zero
// reading. TA produces values in (-1, +1); sentiment falls back to 0; HMM is null
// when the model isn't loaded; debate publishes 0 on LLM failure. The truth signal
// for "this agent is contributing" is therefore: any non-null, non-zero score
// observed in the recent window.
function isAgentHydrated(scores: ScoreDataPoint[], agent: string): boolean {
  return scores.some(s => s.agent_name === agent && s.score !== null && s.score !== 0);
}

export default function AnalysisContent() {
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
        api.agentPerformance.scores(symbol, { agents: "ta,sentiment,debate,regime_hmm", limit: 2000 }),
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
    const interval = setInterval(fetchData, 60_000);
    return () => clearInterval(interval);
  }, [fetchData]);

  return (
    <div className="space-y-4">
      {/* Controls */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <OverlayToggles />
        <div className="flex items-center gap-3 flex-wrap">
          <SymbolSelector />
          <span className="w-px h-5 bg-border" />
          <TimeframeSelector />
        </div>
      </div>

      {/* Chart area */}
      {loading ? (
        <div className="flex items-center justify-center h-[400px] border border-border rounded-md">
          <Loader2 className="w-5 h-5 animate-spin text-muted-foreground" />
          <span className="ml-2 text-sm text-muted-foreground">Loading chart data...</span>
        </div>
      ) : error ? (
        <div className="flex items-center justify-center h-[400px] border border-border rounded-md">
          <p className="text-sm text-red-500">{error}</p>
        </div>
      ) : (
        <div className="space-y-1">
          <div className="border border-border rounded-md p-2">
            <PriceChart data={candles} height={300} />
          </div>

          {visibleOverlays.length > 0 && (
            <div className="border border-border rounded-md p-2">
              <div className="flex items-center justify-between mb-1 px-1">
                <span className="flex items-center gap-1.5 text-xs text-muted-foreground font-medium">
                  Agent Scores
                  <InfoTooltip text="Historical scores from each agent (-1 bearish to +1 bullish). TA updates every 60s, others every 5min. Dark agents are wired but not yet hydrated — see Phase 2 status." />
                </span>
                <div className="flex gap-3 flex-wrap">
                  {visibleOverlays.map((agent) => {
                    const colors: Record<string, string> = { ta: "text-blue-400", sentiment: "text-violet-400", debate: "text-amber-400", regime_hmm: "text-pink-400" };
                    const hydrated = isAgentHydrated(scores, agent);
                    return (
                      <span key={agent} className={`text-xs flex items-center gap-1 ${hydrated ? colors[agent] : "text-muted-foreground/60"}`}>
                        {agent.toUpperCase()}
                        {!hydrated && (
                          <span
                            className="text-[9px] font-mono uppercase tracking-wider px-1 py-0.5 rounded bg-amber-500/10 text-amber-400/80 border border-amber-500/20"
                            title="This agent is wired but not yet producing real signals — see Phase 2 status."
                          >
                            dark
                          </span>
                        )}
                      </span>
                    );
                  })}
                </div>
              </div>
              <AgentScoreOverlay data={scores} visibleAgents={visibleOverlays} height={120} />
            </div>
          )}
        </div>
      )}

      {/* Weights summary */}
      {weights && (
        <div className="border border-border rounded-md p-4">
          <h3 className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground mb-3">
            Current Agent Weights ({symbol})
            <InfoTooltip text="Dynamic weights computed by the Analyst agent via EWMA accuracy. Higher weight = more influence on trade decisions. Dark agents are wired but not yet contributing real signal — see Phase 2 status." />
          </h3>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            {Object.entries(weights.trackers).map(([agent, tracker]) => {
              const weight = weights.weights[agent];
              const defaults: Record<string, number> = { ta: 0.2, sentiment: 0.15, debate: 0.25 };
              const defaultWeight = defaults[agent] ?? 0;
              const delta = weight != null ? weight - defaultWeight : 0;
              const hydrated = isAgentHydrated(scores, agent);
              return (
                <div key={agent} className={`space-y-1 ${hydrated ? "" : "opacity-70"}`}>
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-xs font-medium text-foreground uppercase flex items-center gap-1.5">
                      {agent}
                      {!hydrated && (
                        <span
                          className="text-[9px] font-mono normal-case px-1 py-0.5 rounded bg-amber-500/10 text-amber-400 border border-amber-500/20"
                          title="Wired but not yet hydrated — score is fallback/null, not influencing decisions"
                        >
                          dark
                        </span>
                      )}
                    </span>
                    <span className="text-xs text-muted-foreground">{tracker.samples} samples</span>
                  </div>
                  <div className="flex items-baseline gap-2">
                    <span className="text-lg font-mono tabular-nums text-foreground">{weight != null ? weight.toFixed(3) : "—"}</span>
                    {delta !== 0 && (
                      <span className={`text-xs font-mono tabular-nums ${delta > 0 ? "text-emerald-500" : "text-red-500"}`}>
                        {delta > 0 ? "+" : ""}{delta.toFixed(3)}
                      </span>
                    )}
                  </div>
                  <div className="w-full bg-accent rounded-full h-1">
                    <div className="bg-primary h-1 rounded-full transition-[width] duration-500" style={{ width: `${Math.min(100, (tracker.ewma ?? 0) * 100)}%` }} />
                  </div>
                  <span className="text-[10px] text-muted-foreground">EWMA: {tracker.ewma != null ? (tracker.ewma * 100).toFixed(1) + "%" : "—"}</span>
                </div>
              );
            })}
          </div>
          {Object.keys(weights.trackers).some(a => !isAgentHydrated(scores, a)) && (
            <p className="mt-3 text-[11px] text-muted-foreground border-t border-border pt-3">
              <span className="text-amber-400/80 font-mono uppercase tracking-wider text-[10px] mr-1.5">dark</span>
              agents are wired into the audit chain but not yet producing real signal — they show up so you can see what
              the system <em>would</em> say once the model, source, or LLM is hydrated. Decisions today are driven by
              hydrated agents only.
            </p>
          )}
        </div>
      )}
    </div>
  );
}
