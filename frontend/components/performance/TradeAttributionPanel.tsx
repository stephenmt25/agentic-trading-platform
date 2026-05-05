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

const AGENT_COLORS: Record<string, string> = {
  ta: "text-blue-400",
  sentiment: "text-violet-400",
  debate: "text-amber-400",
};

export function TradeAttributionPanel({ data }: Props) {
  if (!data.length) {
    return (
      <div className="bg-zinc-900/50 rounded-lg border border-zinc-800 p-6 text-center text-sm text-zinc-500">
        No approved trades yet for attribution analysis
      </div>
    );
  }

  return (
    <div className="bg-zinc-900/50 rounded-lg border border-zinc-800 overflow-hidden">
      <div className="px-4 py-3 border-b border-zinc-800">
        <h3 className="text-sm font-medium text-zinc-300 flex items-center gap-1.5">
          Trade Attribution
          <InfoTooltip text="Per-trade breakdown of which agents pushed confidence up or down. Green adjustments helped, red adjustments hurt." />
        </h3>
        <p className="text-xs text-zinc-500 mt-0.5">Which agents influenced each approved trade</p>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-zinc-800 text-zinc-500 text-xs">
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
                <tr key={entry.event_id} className="border-b border-zinc-800/50 hover:bg-zinc-800/30">
                  <td className="px-4 py-2 text-zinc-400 text-xs font-mono whitespace-nowrap">
                    {ts ? ts.toLocaleDateString([], { year: "numeric", month: "short", day: "numeric" }) : "—"}
                  </td>
                  <td className="px-4 py-2 text-zinc-400 text-xs font-mono whitespace-nowrap">
                    {ts ? ts.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" }) : "—"}
                  </td>
                  <td className="text-right px-4 py-2 font-mono text-zinc-300">
                    {entry.input_price ? `$${entry.input_price.toLocaleString()}` : "—"}
                  </td>
                  <td className="text-right px-4 py-2 font-mono text-zinc-400">
                    {confBefore != null ? confBefore.toFixed(3) : "—"}
                  </td>
                  <td className="text-right px-4 py-2 font-mono text-zinc-200">
                    {confAfter != null ? confAfter.toFixed(3) : "—"}
                  </td>
                  {(["ta", "sentiment", "debate"] as const).map((agent) => {
                    const detail = agents?.[agent] as AgentDetail | undefined;
                    const adj = detail?.adjustment ?? 0;
                    return (
                      <td key={agent} className="text-right px-4 py-2 font-mono">
                        <span className={adj > 0 ? "text-green-400" : adj < 0 ? "text-red-400" : "text-zinc-500"}>
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
        <div className="px-4 py-2 text-xs text-zinc-500 border-t border-zinc-800">
          Showing 20 of {data.length} trades
        </div>
      )}
    </div>
  );
}
