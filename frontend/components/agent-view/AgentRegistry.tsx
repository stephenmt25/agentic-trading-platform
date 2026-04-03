"use client";

import { useState, useMemo, useCallback, type MouseEvent } from "react";
import { ChevronDown, ChevronRight, PanelLeftClose, PanelLeft } from "lucide-react";
import { useAgentViewStore } from "@/lib/stores/agentViewStore";
import { useAgentSelection } from "@/lib/hooks/useAgentSelection";
import { AGENT_CATEGORIES, HEALTH_COLORS } from "@/lib/constants/agent-view";
import type { AgentCategory, AgentInfo } from "@/lib/types/telemetry";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatCount(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}k`;
  return String(n);
}

function relativeTime(isoTimestamp: string): string {
  if (!isoTimestamp) return "never";
  const diff = Date.now() - new Date(isoTimestamp).getTime();
  if (diff < 0) return "now";
  const seconds = Math.floor(diff / 1000);
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  return `${hours}h ago`;
}

// ---------------------------------------------------------------------------
// AgentRow
// ---------------------------------------------------------------------------

interface AgentRowProps {
  agent: AgentInfo;
  isSelected: boolean;
  onSelect: (id: string, ctrlKey: boolean) => void;
}

function AgentRow({ agent, isSelected, onSelect }: AgentRowProps) {
  const handleClick = useCallback(
    (e: MouseEvent) => {
      onSelect(agent.agent_id, e.ctrlKey || e.metaKey);
    },
    [agent.agent_id, onSelect]
  );

  return (
    <button
      type="button"
      onClick={handleClick}
      className={`
        flex w-full items-center gap-2 rounded px-3 py-3 md:px-2 md:py-1.5 text-left text-xs
        transition-colors
        ${
          isSelected
            ? "bg-slate-700/60 text-slate-100 border-l-2 border-l-blue-400 md:border-l-0"
            : "text-slate-300 hover:bg-slate-800/80"
        }
      `}
      aria-pressed={isSelected}
      aria-label={`${agent.display_name} - ${agent.health}`}
    >
      {/* Health dot */}
      <span
        className="h-2 w-2 shrink-0 rounded-full"
        style={{ backgroundColor: HEALTH_COLORS[agent.health] }}
        aria-hidden="true"
      />

      {/* Agent name */}
      <span className="flex-1 truncate">{agent.display_name}</span>

      {/* Messages count */}
      <span className="shrink-0 font-mono text-[10px] tabular-nums text-slate-500">
        {formatCount(agent.messages_processed)}
      </span>

      {/* Last active */}
      <span className="shrink-0 font-mono text-[10px] tabular-nums text-slate-600">
        {relativeTime(agent.last_active)}
      </span>
    </button>
  );
}

// ---------------------------------------------------------------------------
// CategorySection
// ---------------------------------------------------------------------------

interface CategorySectionProps {
  category: AgentCategory;
  agents: AgentInfo[];
  isSelected: (id: string) => boolean;
  onSelect: (id: string, ctrlKey: boolean) => void;
}

function CategorySection({
  category,
  agents,
  isSelected,
  onSelect,
}: CategorySectionProps) {
  const [expanded, setExpanded] = useState(true);

  return (
    <div>
      <button
        type="button"
        onClick={() => setExpanded((prev) => !prev)}
        className="flex w-full items-center gap-1.5 px-2 py-1.5 text-left text-[10px] font-semibold uppercase tracking-wider text-slate-500 transition-colors hover:text-slate-400"
        aria-expanded={expanded}
        aria-label={`${category} category, ${agents.length} agents`}
      >
        {expanded ? (
          <ChevronDown className="h-3 w-3" />
        ) : (
          <ChevronRight className="h-3 w-3" />
        )}
        <span className="flex-1">{category}</span>
        <span className="font-mono text-slate-600">{agents.length}</span>
      </button>

      {expanded && (
        <div className="space-y-0.5 pb-1">
          {agents.map((agent) => (
            <AgentRow
              key={agent.agent_id}
              agent={agent}
              isSelected={isSelected(agent.agent_id)}
              onSelect={onSelect}
            />
          ))}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// AgentRegistry
// ---------------------------------------------------------------------------

export function AgentRegistry() {
  const agents = useAgentViewStore((s) => s.agents);
  const { select, toggleSelect, isSelected } = useAgentSelection();
  const [collapsed, setCollapsed] = useState(false);

  // Group agents by category, preserving AGENT_CATEGORIES order
  const grouped = useMemo(() => {
    const agentList = Object.values(agents);
    const map = new Map<AgentCategory, AgentInfo[]>();
    for (const cat of AGENT_CATEGORIES) {
      const members = agentList.filter((a) => a.category === cat);
      if (members.length > 0) {
        map.set(cat, members);
      }
    }
    return map;
  }, [agents]);

  const handleSelect = useCallback(
    (id: string, ctrlKey: boolean) => {
      if (ctrlKey) {
        toggleSelect(id);
      } else {
        select(id);
      }
    },
    [select, toggleSelect]
  );

  return (
    <div
      className={`
        relative flex shrink-0 flex-col bg-[#0d1117]
        transition-[width] duration-200 ease-in-out
        w-full border-r-0
        ${collapsed
          ? "md:w-0 md:overflow-hidden md:border-r-0"
          : "md:w-56 md:border-r md:border-slate-800"
        }
      `}
      role="navigation"
      aria-label="Agent registry"
    >
      {/* Header with collapse toggle */}
      <div className="flex h-9 items-center justify-between border-b border-slate-800 px-3 md:px-2">
        <span className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">
          Agents
        </span>
        <button
          type="button"
          onClick={() => setCollapsed((prev) => !prev)}
          className="hidden md:block rounded p-0.5 text-slate-500 transition-colors hover:bg-slate-800 hover:text-slate-300"
          aria-label={collapsed ? "Expand agent registry" : "Collapse agent registry"}
        >
          <PanelLeftClose className="h-3.5 w-3.5" />
        </button>
      </div>

      {/* Scrollable agent list */}
      <div className="flex-1 overflow-y-auto overflow-x-hidden py-1 px-1 md:px-0">
        {Array.from(grouped.entries()).map(([category, categoryAgents]) => (
          <CategorySection
            key={category}
            category={category}
            agents={categoryAgents}
            isSelected={isSelected}
            onSelect={handleSelect}
          />
        ))}
      </div>

      {/* External expand button when collapsed — desktop only */}
      {collapsed && (
        <button
          type="button"
          onClick={() => setCollapsed(false)}
          className="hidden md:block absolute -right-7 top-1 z-10 rounded-r bg-slate-800 p-1 text-slate-500 transition-colors hover:bg-slate-700 hover:text-slate-300"
          aria-label="Expand agent registry"
        >
          <PanelLeft className="h-3.5 w-3.5" />
        </button>
      )}
    </div>
  );
}
