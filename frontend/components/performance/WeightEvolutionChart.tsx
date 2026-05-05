"use client";

import { InfoTooltip } from "@/components/ui/InfoTooltip";
import { memo, useMemo } from "react";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  Legend,
} from "recharts";

const AGENT_COLORS: Record<string, string> = {
  ta: "#3b82f6",
  sentiment: "#8b5cf6",
  debate: "#f59e0b",
};

interface WeightDataPoint {
  agent_name: string;
  weight: number;
  ewma_accuracy: number;
  sample_count: number;
  recorded_at: string;
}

interface Props {
  data: WeightDataPoint[];
}

function WeightEvolutionChartInner({ data }: Props) {
  const chartData = useMemo(() => {
    const timeMap = new Map<string, Record<string, number>>();

    for (const point of data) {
      const key = point.recorded_at;
      if (!timeMap.has(key)) {
        timeMap.set(key, { timestamp: new Date(key).getTime() / 1000 } as Record<string, number>);
      }
      const row = timeMap.get(key)!;
      row[point.agent_name] = point.weight;
    }

    const merged = Array.from(timeMap.values()).sort(
      (a, b) => (a.timestamp as number) - (b.timestamp as number)
    );

    // Forward-fill so each row carries every agent's most-recent prior
    // weight. Without this the recharts tooltip shows only the one
    // agent that recorded a snapshot at the hovered timestamp.
    const agents = Object.keys(AGENT_COLORS);
    const lastSeen: Record<string, number> = {};
    for (const row of merged) {
      for (const agent of agents) {
        if (typeof row[agent] === "number") {
          lastSeen[agent] = row[agent] as number;
        } else if (typeof lastSeen[agent] === "number") {
          row[agent] = lastSeen[agent];
        }
      }
    }

    return merged;
  }, [data]);

  if (!chartData.length) {
    return (
      <div className="bg-zinc-900/50 rounded-lg border border-zinc-800 p-6 text-center text-sm text-zinc-500">
        No weight history available yet. Weights are recorded every 5 minutes by the Analyst agent.
      </div>
    );
  }

  return (
    <div className="bg-zinc-900/50 rounded-lg border border-zinc-800 p-4">
      <h3 className="text-sm font-medium text-zinc-300 mb-3 flex items-center gap-1.5">
        Weight Evolution
        <InfoTooltip text="How agent weights change over time as the Analyst learns from trade outcomes. Flat lines mean no new position outcomes to learn from." />
      </h3>
      <div className="h-[220px]">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={chartData} margin={{ top: 4, right: 8, bottom: 4, left: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
            <XAxis
              dataKey="timestamp"
              type="number"
              domain={["dataMin", "dataMax"]}
              tickFormatter={(ts: number) => {
                const d = new Date(ts * 1000);
                return `${d.getHours()}:${String(d.getMinutes()).padStart(2, "0")}`;
              }}
              tick={{ fontSize: 10, fill: "#6b7280" }}
              axisLine={{ stroke: "rgba(255,255,255,0.1)" }}
              tickLine={false}
            />
            <YAxis
              domain={[0, "auto"]}
              tick={{ fontSize: 10, fill: "#6b7280" }}
              axisLine={{ stroke: "rgba(255,255,255,0.1)" }}
              tickLine={false}
              width={36}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: "#1f2937",
                border: "1px solid rgba(255,255,255,0.1)",
                borderRadius: 8,
                fontSize: 11,
              }}
              labelFormatter={(ts) => new Date(Number(ts) * 1000).toLocaleString()}
              formatter={(value, name) => [Number(value).toFixed(3), String(name).toUpperCase()]}
            />
            <Legend
              formatter={(value) => <span className="text-xs text-zinc-400">{String(value).toUpperCase()}</span>}
            />
            {Object.keys(AGENT_COLORS).map((agent) => (
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
    </div>
  );
}

export const WeightEvolutionChart = memo(WeightEvolutionChartInner);
