"use client";

import { useMemo } from "react";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ReferenceLine,
  CartesianGrid,
} from "recharts";
import { useAnalysisStore, type AgentOverlay } from "@/lib/stores/analysisStore";

interface ScoreDataPoint {
  symbol: string;
  agent_name: string;
  score: number;
  confidence: number | null;
  recorded_at: string;
}

interface AgentScoreOverlayProps {
  data: ScoreDataPoint[];
  visibleAgents: AgentOverlay[];
  height?: number;
}

const AGENT_COLORS: Record<string, string> = {
  ta: "#3b82f6",
  sentiment: "#8b5cf6",
  debate: "#f59e0b",
  regime_hmm: "#ec4899",
};

const AGENT_LABELS: Record<string, string> = {
  ta: "TA Score",
  sentiment: "Sentiment",
  debate: "Debate",
  regime_hmm: "Regime HMM",
};

export function AgentScoreOverlay({
  data,
  visibleAgents,
  height = 150,
}: AgentScoreOverlayProps) {
  const visibleRange = useAnalysisStore((s) => s.visibleRange);
  const hoveredTime = useAnalysisStore((s) => s.hoveredTime);
  const setHoveredTime = useAnalysisStore((s) => s.setHoveredTime);

  const chartData = useMemo(() => {
    const timeMap = new Map<string, Record<string, number>>();

    for (const point of data) {
      if (!visibleAgents.includes(point.agent_name as AgentOverlay)) continue;
      const key = point.recorded_at;
      if (!timeMap.has(key)) {
        timeMap.set(key, {
          timestamp: new Date(key).getTime() / 1000,
        } as Record<string, number>);
      }
      const row = timeMap.get(key)!;
      row[point.agent_name] = point.score;
    }

    return Array.from(timeMap.values()).sort(
      (a, b) => (a.timestamp as number) - (b.timestamp as number),
    );
  }, [data, visibleAgents]);

  const xDomain = useMemo<[number | string, number | string]>(() => {
    if (visibleRange) return [visibleRange.from, visibleRange.to];
    return ["dataMin", "dataMax"];
  }, [visibleRange]);

  if (!chartData.length) {
    return (
      <div
        style={{ height }}
        className="flex items-center justify-center text-sm text-zinc-500"
      >
        No agent score data available
      </div>
    );
  }

  return (
    <div style={{ height }} className="w-full">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart
          data={chartData}
          margin={{ top: 4, right: 8, bottom: 4, left: 0 }}
          onMouseMove={(state) => {
            const ts = state?.activeLabel;
            if (typeof ts === "number") {
              setHoveredTime(ts, "score");
            }
          }}
          onMouseLeave={() => setHoveredTime(null, null)}
        >
          <CartesianGrid
            strokeDasharray="3 3"
            stroke="rgba(255,255,255,0.04)"
          />
          <XAxis
            dataKey="timestamp"
            type="number"
            domain={xDomain}
            allowDataOverflow
            tickFormatter={(ts: number) => {
              const d = new Date(ts * 1000);
              return `${d.getHours()}:${String(d.getMinutes()).padStart(2, "0")}`;
            }}
            tick={{ fontSize: 10, fill: "#6b7280" }}
            axisLine={{ stroke: "rgba(255,255,255,0.1)" }}
            tickLine={false}
          />
          <YAxis
            domain={[-1, 1]}
            tick={{ fontSize: 10, fill: "#6b7280" }}
            axisLine={{ stroke: "rgba(255,255,255,0.1)" }}
            tickLine={false}
            width={32}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: "#1f2937",
              border: "1px solid rgba(255,255,255,0.1)",
              borderRadius: 8,
              fontSize: 11,
            }}
            labelFormatter={(ts) =>
              new Date(Number(ts) * 1000).toLocaleString()
            }
            formatter={(value, name) => [
              Number(value).toFixed(3),
              AGENT_LABELS[String(name)] || String(name),
            ]}
          />
          <ReferenceLine
            y={0}
            stroke="rgba(255,255,255,0.15)"
            strokeDasharray="4 4"
          />
          {hoveredTime != null && (
            <ReferenceLine
              x={hoveredTime}
              stroke="rgba(255,255,255,0.35)"
              strokeWidth={1}
              ifOverflow="extendDomain"
            />
          )}
          {visibleAgents.map((agent) => (
            <Line
              key={agent}
              dataKey={agent}
              stroke={AGENT_COLORS[agent]}
              strokeWidth={1.5}
              dot={false}
              connectNulls
              isAnimationActive={false}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
