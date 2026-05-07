"use client";

import { useEffect, useState } from "react";
import { Search, Table2, Loader2 } from "lucide-react";
import { CloseReasonPanel } from "./CloseReasonPanel";
import { AgentAttributionSummary } from "./AgentAttributionSummary";
import { RuleHeatmapPanel } from "./RuleHeatmapPanel";
import { TradeAttributesPanel } from "./TradeAttributesPanel";
import { ApprovedTradesPanel } from "./ApprovedTradesPanel";
import { ClosedTradesPanel } from "./ClosedTradesPanel";
import { TradeAttributionPanel } from "./TradeAttributionPanel";
import { api } from "@/lib/api/client";

type Tab =
  | "close_reasons"
  | "agent_stances"
  | "rule_fingerprints"
  | "closed_trades"
  | "approved_trades";

interface Props {
  symbol?: string;
  profileId?: string | null;
}

const TABS: Array<{ id: Tab; label: string; hint: string }> = [
  {
    id: "close_reasons",
    label: "Close reasons",
    hint: "How exits — stop, target, time, manual — are paying off",
  },
  {
    id: "agent_stances",
    label: "Agent stances",
    hint: "Outcomes by which agents agreed or disagreed at decision time",
  },
  {
    id: "rule_fingerprints",
    label: "Rule fingerprints",
    hint: "Which exact condition combinations are winning vs just generating volume",
  },
  {
    id: "closed_trades",
    label: "Closed trades",
    hint: "Slice closed trades by symbol, direction, regime, outcome, close reason, hold duration, hour-of-day, or weekday",
  },
  {
    id: "approved_trades",
    label: "Approved trades",
    hint: "Distribution of decisions that passed every gate (regardless of whether they've closed yet)",
  },
];

// Lazy fetcher for the per-trade attribution table — only runs once the
// user opens the raw table inside the Approved Trades tab.
function ApprovedTradesTableLoader({ symbol }: { symbol?: string }) {
  const [data, setData] = useState<Parameters<typeof TradeAttributionPanel>[0]["data"] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!symbol) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    api.agentPerformance
      .attribution(symbol, 100)
      .then((rows) => {
        if (!cancelled) setData(rows as never);
      })
      .catch((e) => {
        if (!cancelled) setError(e instanceof Error ? e.message : "Failed to load");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [symbol]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-32">
        <Loader2 className="w-4 h-4 animate-spin text-zinc-500" />
      </div>
    );
  }
  if (error) {
    return <div className="text-sm text-red-400 px-1">{error}</div>;
  }
  if (!data) return null;
  return <TradeAttributionPanel data={data} />;
}

// Show/hide toggle wrapping a heavy raw-data panel, used in both the
// Closed Trades and Approved Trades tabs to keep the table out of the
// page until the user explicitly asks for it.
function RawTableToggle({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  const [shown, setShown] = useState(false);
  return (
    <div className="mt-3">
      <button
        type="button"
        onClick={() => setShown((v) => !v)}
        className="inline-flex items-center gap-2 text-xs px-3 py-1.5 rounded bg-zinc-800 hover:bg-zinc-700 text-zinc-200 transition-colors"
      >
        <Table2 className="w-3.5 h-3.5" />
        {shown ? "Hide" : "Open"} {label}
      </button>
      {shown && <div className="mt-3">{children}</div>}
    </div>
  );
}

export function TradeForensicsCard({ symbol, profileId }: Props) {
  const [tab, setTab] = useState<Tab>("close_reasons");

  return (
    <div className="bg-zinc-900/50 rounded-lg border border-zinc-800 overflow-hidden">
      <div className="px-4 py-3 flex items-center gap-3 border-b border-zinc-800">
        <Search className="w-4 h-4 text-amber-400/80" />
        <div className="flex-1">
          <div className="text-sm font-medium text-zinc-200">Trade Forensics</div>
          <div className="text-xs text-zinc-500 mt-0.5">
            Reconstruct what fired, what agreed, and what actually paid off across closed trades.
          </div>
        </div>
      </div>

      <div>
        <div role="tablist" className="flex flex-wrap gap-1 px-3 pt-3">
          {TABS.map((t) => {
            const active = t.id === tab;
            return (
              <button
                key={t.id}
                role="tab"
                aria-selected={active}
                onClick={() => setTab(t.id)}
                className={`px-3 py-1.5 text-xs rounded transition-colors ${
                  active
                    ? "bg-zinc-800 text-zinc-100"
                    : "text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/60"
                }`}
              >
                {t.label}
              </button>
            );
          })}
        </div>
        <div className="px-3 pt-1 pb-3">
          <p className="text-[11px] text-zinc-500 px-1 mb-2">
            {TABS.find((t) => t.id === tab)?.hint}
          </p>
          {tab === "close_reasons" && (
            <CloseReasonPanel symbol={symbol} profileId={profileId} />
          )}
          {tab === "agent_stances" && (
            <AgentAttributionSummary symbol={symbol} profileId={profileId} />
          )}
          {tab === "rule_fingerprints" && (
            <RuleHeatmapPanel symbol={symbol} profileId={profileId} />
          )}
          {tab === "closed_trades" && (
            <>
              <TradeAttributesPanel symbol={symbol} profileId={profileId} />
              <RawTableToggle label="closed trades table">
                <ClosedTradesPanel symbol={symbol} limit={200} />
              </RawTableToggle>
            </>
          )}
          {tab === "approved_trades" && (
            <>
              <ApprovedTradesPanel symbol={symbol} profileId={profileId} />
              <RawTableToggle label="approved trades table">
                <ApprovedTradesTableLoader symbol={symbol} />
              </RawTableToggle>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
