"use client";

import { InfoTooltip } from "@/components/ui/InfoTooltip";

const AGENT_DEFAULTS: Record<string, number> = {
  ta: 0.20,
  sentiment: 0.15,
  debate: 0.25,
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
      <div className="bg-bg-panel/50 rounded-lg border border-border-subtle p-6 text-center text-sm text-fg-muted">
        No weight data available
      </div>
    );
  }

  const agents = Object.keys(AGENT_DEFAULTS);

  return (
    <div className="bg-bg-panel/50 rounded-lg border border-border-subtle overflow-hidden">
      <div className="px-4 py-3 border-b border-border-subtle">
        <h3 className="text-sm font-medium text-fg-secondary flex items-center gap-1.5">
          Agent Accuracy &amp; Weights
          <InfoTooltip text="EWMA accuracy tracks how often each agent's direction aligned with winning trades. Weights are adjusted based on accuracy — higher accuracy = more influence." />
        </h3>
      </div>
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border-subtle text-fg-muted text-xs">
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
              <tr key={agent} className="border-b border-border-subtle/50 hover:bg-bg-rowhover/30">
                <td className="px-4 py-3">
                  <div className="flex items-center gap-2">
                    {/* ADR-012: agent identities alias to accent — differentiation
                        is by label + row position, never by hue. */}
                    <span className="w-2 h-2 rounded-full bg-accent-500" />
                    <span className="font-medium text-fg uppercase">{agent}</span>
                  </div>
                </td>
                <td className="text-right px-4 py-3 num-tabular text-fg-secondary">
                  {(ewma * 100).toFixed(1)}%
                </td>
                <td className="text-right px-4 py-3 num-tabular text-fg-muted">
                  {samples}
                </td>
                <td className="text-right px-4 py-3 num-tabular text-fg">
                  {currentWeight.toFixed(3)}
                </td>
                <td className="text-right px-4 py-3 num-tabular text-fg-muted">
                  {defaultWeight.toFixed(3)}
                </td>
                <td className="text-right px-4 py-3 num-tabular">
                  <span className={delta > 0 ? "text-bid-400" : delta < 0 ? "text-ask-400" : "text-fg-muted"}>
                    {delta > 0 ? "+" : ""}{delta.toFixed(3)}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <div className="w-full bg-bg-raised rounded-full h-1.5">
                    <div
                      className="h-1.5 rounded-full transition-all bg-accent-500"
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
