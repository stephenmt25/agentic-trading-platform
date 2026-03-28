"use client";

import { Box, Cpu } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { useAgentSelection } from "@/lib/hooks/useAgentSelection";
import { useAgentViewStore } from "@/lib/stores/agentViewStore";
import { AGENT_TYPE_COLORS } from "@/lib/constants/agent-view";
import { AgentInputStream } from "./AgentInputStream";
import { AgentDecisionState } from "./AgentDecisionState";
import { AgentOutputStream } from "./AgentOutputStream";

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function AgentDetail() {
  const { selectedIds } = useAgentSelection();
  const selectedId = selectedIds[0] ?? null;
  const agent = useAgentViewStore((s) => selectedId ? s.agents[selectedId] : undefined);

  if (!selectedId || !agent) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-3 bg-[#0d1117]">
        <Box className="h-8 w-8 text-slate-600" />
        <span className="text-sm text-slate-500">
          Select an agent from the registry
        </span>
      </div>
    );
  }

  const typeColor = AGENT_TYPE_COLORS[agent.agent_type];

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
