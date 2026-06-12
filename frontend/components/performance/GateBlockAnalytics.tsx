"use client";

import { memo } from "react";
import { InfoTooltip } from "@/components/ui/InfoTooltip";
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

/**
 * Outcome → token mapping stays inside the six chromatic semantic roles
 * (DESIGN.md): approved = bid (positive), hard violations = danger,
 * risk rejections = ask, advisory blocks = warn, human/system gates =
 * accent, blacklist = neutral. Category labels on the Y axis carry the
 * identity; color carries meaning only.
 */
const OUTCOME_COLORS: Record<string, string> = {
  APPROVED: "var(--color-bid-500)",
  BLOCKED_ABSTENTION: "var(--color-warn-500)",
  BLOCKED_REGIME: "var(--color-warn-600)",
  BLOCKED_CIRCUIT_BREAKER: "var(--color-danger-500)",
  BLOCKED_BLACKLIST: "var(--color-neutral-500)",
  BLOCKED_RISK: "var(--color-ask-500)",
  BLOCKED_HITL: "var(--color-accent-500)",
  BLOCKED_VALIDATION: "var(--color-accent-400)",
};

interface Props {
  data: {
    total_decisions: number;
    outcome_counts: Record<string, number>;
    gate_details: Record<string, { passed: number; blocked: number; reasons: Record<string, number> }>;
  } | null;
}

function GateBlockAnalyticsInner({ data }: Props) {
  if (!data || data.total_decisions === 0) {
    return (
      <div className="bg-bg-panel/50 rounded-lg border border-border-subtle p-6 text-center text-sm text-fg-muted">
        No decision data available yet
      </div>
    );
  }

  const chartData = Object.entries(data.outcome_counts)
    .map(([outcome, count]) => ({
      name: outcome.replace("BLOCKED_", "").replace(/_/g, " "),
      count,
      color: OUTCOME_COLORS[outcome] || "var(--color-neutral-500)",
    }))
    .sort((a, b) => b.count - a.count);

  return (
    <div className="bg-bg-panel/50 rounded-lg border border-border-subtle p-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-medium text-fg-secondary flex items-center gap-1.5">
          Decision Outcomes
          <InfoTooltip text="How many signals were approved vs blocked by each gate. High abstention means strategy rules rarely trigger." />
        </h3>
        <span className="text-xs text-fg-muted">{data.total_decisions} total</span>
      </div>
      <div className="h-[220px]">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={chartData} layout="vertical" margin={{ left: 80, right: 8, top: 4, bottom: 4 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border-subtle)" horizontal={false} />
            <XAxis type="number" tick={{ fontSize: 10, fill: "var(--color-fg-muted)" }} axisLine={false} tickLine={false} />
            <YAxis
              type="category"
              dataKey="name"
              tick={{ fontSize: 10, fill: "var(--color-neutral-300)" }}
              axisLine={false}
              tickLine={false}
              width={75}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: "var(--color-bg-raised)",
                border: "1px solid var(--color-border-strong)",
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
        <div className="mt-3 pt-3 border-t border-border-subtle">
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
            {Object.entries(data.gate_details).map(([gate, detail]) => {
              const total = detail.passed + detail.blocked;
              const passRate = total > 0 ? (detail.passed / total) * 100 : 0;
              return (
                <div key={gate} className="text-xs">
                  <div className="flex items-center justify-between">
                    <span className="text-fg-muted capitalize">{gate.replace(/_/g, " ")}</span>
                    <span className={passRate > 80 ? "text-bid-400" : passRate > 50 ? "text-warn-400" : "text-ask-400"}>
                      {passRate.toFixed(0)}%
                    </span>
                  </div>
                  <div className="w-full bg-bg-raised rounded-full h-1 mt-1">
                    <div
                      className="bg-bid-500/60 h-1 rounded-full"
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

export const GateBlockAnalytics = memo(GateBlockAnalyticsInner);
