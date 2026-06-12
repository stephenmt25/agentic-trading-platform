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

/**
 * Per ADR-012, agents never get chromatic identities: every series draws
 * in the accent hue and differentiates by dash pattern + label (the
 * tooltip and legend carry the agent name). Key order doubles as the
 * agent list for the forward-fill below — keep ta/sentiment/debate.
 */
const AGENT_SERIES: Record<string, { dash?: string }> = {
  ta: {},
  sentiment: { dash: "6 3" },
  debate: { dash: "2 2" },
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
    const agents = Object.keys(AGENT_SERIES);
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
      <div className="bg-bg-panel/50 rounded-lg border border-border-subtle p-6 text-center text-sm text-fg-muted">
        No weight history available yet. Weights are recorded every 5 minutes by the Analyst agent.
      </div>
    );
  }

  return (
    <div className="bg-bg-panel/50 rounded-lg border border-border-subtle p-4">
      <h3 className="text-sm font-medium text-fg-secondary mb-3 flex items-center gap-1.5">
        Weight Evolution
        <InfoTooltip text="How agent weights change over time as the Analyst learns from trade outcomes. Flat lines mean no new position outcomes to learn from." />
      </h3>
      <div className="h-[220px]">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={chartData} margin={{ top: 4, right: 8, bottom: 4, left: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border-subtle)" />
            <XAxis
              dataKey="timestamp"
              type="number"
              domain={["dataMin", "dataMax"]}
              tickFormatter={(ts: number) => {
                const d = new Date(ts * 1000);
                return `${d.getHours()}:${String(d.getMinutes()).padStart(2, "0")}`;
              }}
              tick={{ fontSize: 10, fill: "var(--color-fg-muted)" }}
              axisLine={{ stroke: "var(--color-border-strong)" }}
              tickLine={false}
            />
            <YAxis
              domain={[0, "auto"]}
              tick={{ fontSize: 10, fill: "var(--color-fg-muted)" }}
              axisLine={{ stroke: "var(--color-border-strong)" }}
              tickLine={false}
              width={36}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: "var(--color-bg-raised)",
                border: "1px solid var(--color-border-strong)",
                borderRadius: 8,
                fontSize: 11,
              }}
              labelFormatter={(ts) => new Date(Number(ts) * 1000).toLocaleString()}
              formatter={(value, name) => [Number(value).toFixed(3), String(name).toUpperCase()]}
            />
            <Legend
              formatter={(value) => <span className="text-xs text-fg-muted">{String(value).toUpperCase()}</span>}
            />
            {Object.keys(AGENT_SERIES).map((agent) => (
              <Line
                key={agent}
                dataKey={agent}
                stroke="var(--color-accent-500)"
                strokeDasharray={AGENT_SERIES[agent].dash}
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
