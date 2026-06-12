"use client";

import { InfoTooltip } from "@/components/ui/InfoTooltip";

interface AgentDetail {
  score: number | null;
  weight: number;
  adjustment: number;
}

interface AttributionEntry {
  event_id: string;
  symbol: string;
  outcome: string;
  input_price: number | null;
  agents: {
    ta?: AgentDetail;
    sentiment?: AgentDetail;
    debate?: AgentDetail;
    confidence_before?: number;
    confidence_after?: number;
  } | null;
  created_at: string | null;
}

interface Props {
  data: AttributionEntry[];
}

export function TradeAttributionPanel({ data }: Props) {
  if (!data.length) {
    return (
      <div className="bg-bg-panel/50 rounded-lg border border-border-subtle p-6 text-center text-sm text-fg-muted">
        No approved trades yet for attribution analysis
      </div>
    );
  }

  return (
    <div className="bg-bg-panel/50 rounded-lg border border-border-subtle overflow-hidden">
      <div className="px-4 py-3 border-b border-border-subtle">
        <h3 className="text-sm font-medium text-fg-secondary flex items-center gap-1.5">
          Trade Attribution
          <InfoTooltip text="Per-trade breakdown of which agents pushed confidence up or down. Green adjustments helped, red adjustments hurt." />
        </h3>
        <p className="text-xs text-fg-muted mt-0.5">Which agents influenced each approved trade</p>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border-subtle text-fg-muted text-xs">
              <th className="text-left px-4 py-2 font-medium">Date</th>
              <th className="text-left px-4 py-2 font-medium">Time</th>
              <th className="text-right px-4 py-2 font-medium">Price</th>
              <th className="text-right px-4 py-2 font-medium">Conf Before</th>
              <th className="text-right px-4 py-2 font-medium">Conf After</th>
              <th className="text-right px-4 py-2 font-medium">TA Adj</th>
              <th className="text-right px-4 py-2 font-medium">Sent Adj</th>
              <th className="text-right px-4 py-2 font-medium">Debate Adj</th>
            </tr>
          </thead>
          <tbody>
            {data.slice(0, 20).map((entry) => {
              const agents = entry.agents as AttributionEntry["agents"];
              const confBefore = agents?.confidence_before;
              const confAfter = agents?.confidence_after;
              const ts = entry.created_at ? new Date(entry.created_at) : null;

              return (
                <tr key={entry.event_id} className="border-b border-border-subtle/50 hover:bg-bg-rowhover/30">
                  <td className="px-4 py-2 text-fg-muted text-xs num-tabular whitespace-nowrap">
                    {ts ? ts.toLocaleDateString([], { year: "numeric", month: "short", day: "numeric" }) : "—"}
                  </td>
                  <td className="px-4 py-2 text-fg-muted text-xs num-tabular whitespace-nowrap">
                    {ts ? ts.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" }) : "—"}
                  </td>
                  <td className="text-right px-4 py-2 num-tabular text-fg-secondary">
                    {entry.input_price ? `$${entry.input_price.toLocaleString()}` : "—"}
                  </td>
                  <td className="text-right px-4 py-2 num-tabular text-fg-muted">
                    {confBefore != null ? confBefore.toFixed(3) : "—"}
                  </td>
                  <td className="text-right px-4 py-2 num-tabular text-fg">
                    {confAfter != null ? confAfter.toFixed(3) : "—"}
                  </td>
                  {(["ta", "sentiment", "debate"] as const).map((agent) => {
                    const detail = agents?.[agent] as AgentDetail | undefined;
                    const adj = detail?.adjustment ?? 0;
                    return (
                      <td key={agent} className="text-right px-4 py-2 num-tabular">
                        <span className={adj > 0 ? "text-bid-400" : adj < 0 ? "text-ask-400" : "text-fg-muted"}>
                          {adj > 0 ? "+" : ""}{adj.toFixed(3)}
                        </span>
                      </td>
                    );
                  })}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {data.length > 20 && (
        <div className="px-4 py-2 text-xs text-fg-muted border-t border-border-subtle">
          Showing 20 of {data.length} trades
        </div>
      )}
    </div>
  );
}
