"use client";

import { InfoTooltip } from "@/components/ui/InfoTooltip";

const AGENT_DEFAULTS: Record<string, number> = {
  ta: 0.20,
  sentiment: 0.15,
  debate: 0.25,
};

const AGENT_COLORS: Record<string, string> = {
  ta: "bg-blue-500",
  sentiment: "bg-violet-500",
  debate: "bg-amber-500",
};

interface Props {
  weights: {
    weights: Record<string, number>;
    trackers: Record<string, { ewma: number | null; samples: number; last_updated: string | null }>;
  } | null;
}

export function AgentAccuracyTable({ weights }: Props) {
  if (!weights) {
    return (
      <div className="bg-zinc-900/50 rounded-lg border border-zinc-800 p-6 text-center text-sm text-zinc-500">
        No weight data available
      </div>
    );
  }

  const agents = Object.keys(AGENT_DEFAULTS);

  return (
    <div className="bg-zinc-900/50 rounded-lg border border-zinc-800 overflow-hidden">
      <div className="px-4 py-3 border-b border-zinc-800">
        <h3 className="text-sm font-medium text-zinc-300 flex items-center gap-1.5">
          Agent Accuracy & Weights
          <InfoTooltip text="EWMA accuracy tracks how often each agent's direction aligned with winning trades. Weights are adjusted based on accuracy — higher accuracy = more influence." />
        </h3>
      </div>
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-zinc-800 text-zinc-500 text-xs">
            <th className="text-left px-4 py-2 font-medium">Agent</th>
            <th className="text-right px-4 py-2 font-medium">EWMA Accuracy</th>
            <th className="text-right px-4 py-2 font-medium">Samples</th>
            <th className="text-right px-4 py-2 font-medium">Current Weight</th>
            <th className="text-right px-4 py-2 font-medium">Default</th>
            <th className="text-right px-4 py-2 font-medium">Delta</th>
            <th className="px-4 py-2 font-medium">Accuracy</th>
          </tr>
        </thead>
        <tbody>
          {agents.map((agent) => {
            const tracker = weights.trackers[agent];
            const currentWeight = weights.weights[agent] ?? AGENT_DEFAULTS[agent];
            const defaultWeight = AGENT_DEFAULTS[agent];
            const delta = currentWeight - defaultWeight;
            const ewma = tracker?.ewma ?? 0;
            const samples = tracker?.samples ?? 0;

            return (
              <tr key={agent} className="border-b border-zinc-800/50 hover:bg-zinc-800/30">
                <td className="px-4 py-3">
                  <div className="flex items-center gap-2">
                    <span className={`w-2 h-2 rounded-full ${AGENT_COLORS[agent]}`} />
                    <span className="font-medium text-zinc-200 uppercase">{agent}</span>
                  </div>
                </td>
                <td className="text-right px-4 py-3 font-mono text-zinc-300">
                  {(ewma * 100).toFixed(1)}%
                </td>
                <td className="text-right px-4 py-3 font-mono text-zinc-400">
                  {samples}
                </td>
                <td className="text-right px-4 py-3 font-mono text-zinc-200">
                  {currentWeight.toFixed(3)}
                </td>
                <td className="text-right px-4 py-3 font-mono text-zinc-500">
                  {defaultWeight.toFixed(3)}
                </td>
                <td className="text-right px-4 py-3 font-mono">
                  <span className={delta > 0 ? "text-green-400" : delta < 0 ? "text-red-400" : "text-zinc-500"}>
                    {delta > 0 ? "+" : ""}{delta.toFixed(3)}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <div className="w-full bg-zinc-800 rounded-full h-1.5">
                    <div
                      className={`h-1.5 rounded-full transition-all ${AGENT_COLORS[agent]}`}
                      style={{ width: `${Math.min(100, ewma * 100)}%` }}
                    />
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
