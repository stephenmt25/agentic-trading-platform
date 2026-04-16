"use client";

import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  Cell,
} from "recharts";

const OUTCOME_COLORS: Record<string, string> = {
  APPROVED: "#22c55e",
  BLOCKED_ABSTENTION: "#f59e0b",
  BLOCKED_REGIME: "#ec4899",
  BLOCKED_CIRCUIT_BREAKER: "#ef4444",
  BLOCKED_BLACKLIST: "#6b7280",
  BLOCKED_RISK: "#f97316",
  BLOCKED_HITL: "#8b5cf6",
  BLOCKED_VALIDATION: "#3b82f6",
};

interface Props {
  data: {
    total_decisions: number;
    outcome_counts: Record<string, number>;
    gate_details: Record<string, { passed: number; blocked: number; reasons: Record<string, number> }>;
  } | null;
}

export function GateBlockAnalytics({ data }: Props) {
  if (!data || data.total_decisions === 0) {
    return (
      <div className="bg-zinc-900/50 rounded-lg border border-zinc-800 p-6 text-center text-sm text-zinc-500">
        No decision data available yet
      </div>
    );
  }

  const chartData = Object.entries(data.outcome_counts)
    .map(([outcome, count]) => ({
      name: outcome.replace("BLOCKED_", "").replace(/_/g, " "),
      count,
      color: OUTCOME_COLORS[outcome] || "#6b7280",
    }))
    .sort((a, b) => b.count - a.count);

  return (
    <div className="bg-zinc-900/50 rounded-lg border border-zinc-800 p-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-medium text-zinc-300">Decision Outcomes</h3>
        <span className="text-xs text-zinc-500">{data.total_decisions} total</span>
      </div>
      <div className="h-[220px]">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={chartData} layout="vertical" margin={{ left: 80, right: 8, top: 4, bottom: 4 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" horizontal={false} />
            <XAxis type="number" tick={{ fontSize: 10, fill: "#6b7280" }} axisLine={false} tickLine={false} />
            <YAxis
              type="category"
              dataKey="name"
              tick={{ fontSize: 10, fill: "#9ca3af" }}
              axisLine={false}
              tickLine={false}
              width={75}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: "#1f2937",
                border: "1px solid rgba(255,255,255,0.1)",
                borderRadius: 8,
                fontSize: 11,
              }}
            />
            <Bar dataKey="count" radius={[0, 4, 4, 0]}>
              {chartData.map((entry, idx) => (
                <Cell key={idx} fill={entry.color} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Gate pass/block summary */}
      {Object.keys(data.gate_details).length > 0 && (
        <div className="mt-3 pt-3 border-t border-zinc-800">
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
            {Object.entries(data.gate_details).map(([gate, detail]) => {
              const total = detail.passed + detail.blocked;
              const passRate = total > 0 ? (detail.passed / total) * 100 : 0;
              return (
                <div key={gate} className="text-xs">
                  <div className="flex items-center justify-between">
                    <span className="text-zinc-400 capitalize">{gate.replace(/_/g, " ")}</span>
                    <span className={passRate > 80 ? "text-green-400" : passRate > 50 ? "text-amber-400" : "text-red-400"}>
                      {passRate.toFixed(0)}%
                    </span>
                  </div>
                  <div className="w-full bg-zinc-800 rounded-full h-1 mt-1">
                    <div
                      className="bg-green-500/60 h-1 rounded-full"
                      style={{ width: `${passRate}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
