"use client";

import { useState } from "react";
import { Box, ChevronDown, ChevronRight, Cpu, ArrowLeft, ArrowRight, ArrowDown } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { useAgentSelection } from "@/lib/hooks/useAgentSelection";
import { useAgentViewStore } from "@/lib/stores/agentViewStore";
import { useIsMobile } from "@/lib/hooks/useMediaQuery";
import { AGENT_TYPE_COLORS } from "@/lib/constants/agent-view";
import { AgentInputStream } from "./AgentInputStream";
import { AgentDecisionState } from "./AgentDecisionState";
import { AgentOutputStream } from "./AgentOutputStream";
import { DataSourceIndicator } from "./DataSourceBadge";

// ---------------------------------------------------------------------------
// Collapsible Section (mobile accordion)
// ---------------------------------------------------------------------------

interface CollapsibleSectionProps {
  title: string;
  defaultOpen?: boolean;
  children: React.ReactNode;
}

function CollapsibleSection({
  title,
  defaultOpen = true,
  children,
}: CollapsibleSectionProps) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <div className="border-b border-slate-700/50">
      <button
        type="button"
        onClick={() => setOpen((p) => !p)}
        className="flex w-full items-center gap-2 px-4 py-3 text-xs font-semibold text-slate-300 active:bg-slate-800/50"
        aria-expanded={open}
      >
        {open ? (
          <ChevronDown className="h-4 w-4 text-slate-500" />
        ) : (
          <ChevronRight className="h-4 w-4 text-slate-500" />
        )}
        {title}
      </button>
      {open && <div className="min-h-[200px] max-h-[50vh]">{children}</div>}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function AgentDetail() {
  const { selectedIds } = useAgentSelection();
  const selectedId = selectedIds[0] ?? null;
  const agent = useAgentViewStore((s) =>
    selectedId ? s.agents[selectedId] : undefined,
  );
  const isMobile = useIsMobile();

  if (!selectedId || !agent) {
    return (
      <div className="flex h-full flex-col items-center justify-center bg-[#0d1117] px-6">
        <div className="max-w-sm space-y-5">
          <div className="text-center">
            <Box className="h-8 w-8 text-slate-600 mx-auto mb-2" />
            <h3 className="text-sm font-semibold text-slate-300 mb-1">Agent Monitor</h3>
            <p className="text-xs text-slate-500">Real-time view of all pipeline agents and their decisions.</p>
          </div>

          <div className="space-y-3">
            <div className="flex items-start gap-3 p-2.5 rounded-md border border-slate-800/50">
              <ArrowLeft className="w-4 h-4 text-emerald-500 shrink-0 mt-0.5" />
              <div>
                <div className="text-xs font-medium text-slate-300">Agent Registry</div>
                <div className="text-[11px] text-slate-500 mt-0.5">Browse all agents grouped by role. Green = healthy, amber = degraded, red = error.</div>
              </div>
            </div>
            <div className="flex items-start gap-3 p-2.5 rounded-md border border-primary/20 bg-primary/5">
              <Cpu className="w-4 h-4 text-primary shrink-0 mt-0.5" />
              <div>
                <div className="text-xs font-medium text-slate-300">Agent Detail</div>
                <div className="text-[11px] text-slate-500 mt-0.5">Click any agent on the left to view its input stream, decision state, and output stream.</div>
              </div>
            </div>
            <div className="flex items-start gap-3 p-2.5 rounded-md border border-slate-800/50">
              <ArrowRight className="w-4 h-4 text-amber-500 shrink-0 mt-0.5" />
              <div>
                <div className="text-xs font-medium text-slate-300">Message Flow</div>
                <div className="text-[11px] text-slate-500 mt-0.5">Live message stream showing data flowing between agents in real-time.</div>
              </div>
            </div>
            <div className="flex items-start gap-3 p-2.5 rounded-md border border-slate-800/50">
              <ArrowDown className="w-4 h-4 text-violet-500 shrink-0 mt-0.5" />
              <div>
                <div className="text-xs font-medium text-slate-300">Quick Stats</div>
                <div className="text-[11px] text-slate-500 mt-0.5">System-wide metrics: orders, fills, win rate, drawdown, and active positions.</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  const typeColor = AGENT_TYPE_COLORS[agent.agent_type];

  // ── Mobile: scrollable accordion cards ────────────────────────────────
  if (isMobile) {
    return (
      <div className="flex h-full flex-col overflow-y-auto bg-[#0d1117]">
        {/* Header */}
        <div className="flex items-center gap-3 border-b border-slate-800 px-4 py-3">
          <Cpu className="h-5 w-5 text-slate-400" />
          <div className="flex-1 min-w-0">
            <span className="text-sm font-semibold text-slate-200">
              {agent.display_name}
            </span>
            <div className="flex items-center gap-2 mt-0.5 flex-wrap">
              <Badge
                variant="secondary"
                className="px-1.5 text-[10px] font-mono font-medium"
                style={{
                  backgroundColor: `${typeColor}20`,
                  color: typeColor,
                }}
              >
                {agent.agent_type}
              </Badge>
              <DataSourceIndicator data_sources={agent.data_sources} />
              <span className="font-mono text-[10px] text-slate-500 truncate">
                {agent.agent_id}
              </span>
            </div>
          </div>
          <span
            className="h-2.5 w-2.5 rounded-full shrink-0"
            style={{
              backgroundColor:
                agent.health === "healthy"
                  ? "#22c55e"
                  : agent.health === "degraded"
                    ? "#eab308"
                    : agent.health === "error"
                      ? "#ef4444"
                      : "#6b7280",
            }}
          />
        </div>

        {/* Accordion sections */}
        <CollapsibleSection title="Input Stream" defaultOpen>
          <AgentInputStream agentId={selectedId} />
        </CollapsibleSection>

        <CollapsibleSection title="Decision State" defaultOpen={false}>
          <AgentDecisionState agentId={selectedId} />
        </CollapsibleSection>

        <CollapsibleSection title="Output Stream" defaultOpen={false}>
          <AgentOutputStream agentId={selectedId} />
        </CollapsibleSection>
      </div>
    );
  }

  // ── Desktop: three-section vertical split ─────────────────────────────
  return (
    <div className="flex h-full flex-col bg-[#0d1117]">
      {/* Header */}
      <div className="flex items-center gap-3 border-b border-slate-800 px-4 py-2.5">
        <Cpu className="h-4 w-4 text-slate-400" />
        <span className="text-sm font-semibold text-slate-200">
          {agent.display_name}
        </span>
        <Badge
          variant="secondary"
          className="px-1.5 text-[10px] font-mono font-medium"
          style={{ backgroundColor: `${typeColor}20`, color: typeColor }}
        >
          {agent.agent_type}
        </Badge>
        <DataSourceIndicator data_sources={agent.data_sources} />
        <span className="ml-auto font-mono text-[10px] text-slate-500">
          {agent.agent_id}
        </span>
      </div>

      {/* Three-section vertical split */}
      <div className="flex flex-1 min-h-0 flex-col">
        {/* Input Stream - top third */}
        <div className="flex-1 min-h-0 border-b border-slate-700/50">
          <AgentInputStream agentId={selectedId} />
        </div>

        {/* Decision State - middle third */}
        <div className="flex-1 min-h-0 border-b border-slate-700/50">
          <AgentDecisionState agentId={selectedId} />
        </div>

        {/* Output Stream - bottom third */}
        <div className="flex-1 min-h-0">
          <AgentOutputStream agentId={selectedId} />
        </div>
      </div>
    </div>
  );
}
