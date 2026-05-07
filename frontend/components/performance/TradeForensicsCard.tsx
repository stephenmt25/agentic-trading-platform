"use client";

import { useState } from "react";
import { ChevronDown, ChevronRight, Search } from "lucide-react";
import { CloseReasonPanel } from "./CloseReasonPanel";
import { AgentAttributionSummary } from "./AgentAttributionSummary";
import { RuleHeatmapPanel } from "./RuleHeatmapPanel";

type Tab = "close_reasons" | "agent_stances" | "rule_fingerprints";

interface Props {
  symbol?: string;
  profileId?: string | null;
  defaultOpen?: boolean;
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
];

export function TradeForensicsCard({ symbol, profileId, defaultOpen = false }: Props) {
  const [open, setOpen] = useState(defaultOpen);
  const [tab, setTab] = useState<Tab>("close_reasons");

  return (
    <div className="bg-zinc-900/50 rounded-lg border border-zinc-800 overflow-hidden">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="w-full px-4 py-3 flex items-center gap-3 text-left hover:bg-zinc-800/40 transition-colors"
        aria-expanded={open}
      >
        <span className="text-zinc-500">
          {open ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
        </span>
        <Search className="w-4 h-4 text-amber-400/80" />
        <div className="flex-1">
          <div className="text-sm font-medium text-zinc-200">Trade Forensics</div>
          <div className="text-xs text-zinc-500 mt-0.5">
            Reconstruct what fired, what agreed, and what actually paid off across closed trades.
          </div>
        </div>
        {!open && (
          <span className="text-[11px] text-zinc-500 hidden sm:inline">
            click to explore
          </span>
        )}
      </button>

      {open && (
        <div className="border-t border-zinc-800">
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
          </div>
        </div>
      )}
    </div>
  );
}
