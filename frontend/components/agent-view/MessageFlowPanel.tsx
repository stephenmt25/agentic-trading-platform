"use client";

import { useCallback, useMemo, useRef, useState } from "react";
import { Virtuoso, type VirtuosoHandle } from "react-virtuoso";
import {
  ArrowDown,
  ChevronLeft,
  ChevronRight,
  Filter,
  MessageSquare,
  Search,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { useAgentViewStore } from "@/lib/stores/agentViewStore";
import { AGENT_TYPE_COLORS, AGENT_REGISTRY } from "@/lib/constants/agent-view";
import type {
  AgentTelemetryEvent,
  AgentType,
  TelemetryEventType,
} from "@/lib/types/telemetry";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const EVENT_TYPE_OPTIONS: TelemetryEventType[] = [
  "state_update",
  "input_received",
  "output_emitted",
  "decision_trace",
  "health_check",
  "error",
  "config_change",
];

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatTimestamp(iso: string): string {
  try {
    const d = new Date(iso);
    const h = String(d.getHours()).padStart(2, "0");
    const m = String(d.getMinutes()).padStart(2, "0");
    const s = String(d.getSeconds()).padStart(2, "0");
    const ms = String(d.getMilliseconds()).padStart(3, "0");
    return `${h}:${m}:${s}.${ms}`;
  } catch {
    return iso;
  }
}

function resolveAgentType(agentId: string): AgentType | undefined {
  return AGENT_REGISTRY.find((a) => a.agent_id === agentId)?.agent_type;
}

function resolveDisplayName(agentId: string): string {
  return (
    AGENT_REGISTRY.find((a) => a.agent_id === agentId)?.display_name ??
    agentId
  );
}

// ---------------------------------------------------------------------------
// Row Component
// ---------------------------------------------------------------------------

interface FlowRowProps {
  event: AgentTelemetryEvent;
}

function FlowRow({ event }: FlowRowProps) {
  const fromId = event.source_agent ?? event.agent_id;
  const toId = event.target_agent ?? "---";

  const fromType = resolveAgentType(fromId);
  const toType = toId !== "---" ? resolveAgentType(toId) : undefined;

  const fromColor = fromType ? AGENT_TYPE_COLORS[fromType] : "#94a3b8";
  const toColor = toType ? AGENT_TYPE_COLORS[toType] : "#64748b";

  const messageType =
    (event.payload.message_type as string | undefined) ??
    event.event_type;

  return (
    <div className="flex items-center gap-2 border-b border-slate-800/40 px-2 py-1 text-[10px]">
      {/* Timestamp */}
      <span className="shrink-0 font-mono text-slate-500">
        {formatTimestamp(event.timestamp)}
      </span>

      {/* From -> To */}
      <span className="shrink-0 flex items-center gap-0.5 min-w-0">
        <span className="truncate font-mono font-medium" style={{ color: fromColor }}>
          {fromId}
        </span>
        <span className="text-slate-600">&rarr;</span>
        <span className="truncate font-mono font-medium" style={{ color: toColor }}>
          {toId}
        </span>
      </span>

      {/* Message type */}
      <span className="shrink-0 truncate rounded bg-slate-800 px-1 py-0.5 font-mono text-slate-400">
        {messageType}
      </span>

      {/* Latency */}
      {event.latency_ms !== undefined && (
        <span className="ml-auto shrink-0 font-mono text-slate-500">
          {event.latency_ms.toFixed(1)}ms
        </span>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function MessageFlowPanel() {
  const [collapsed, setCollapsed] = useState(false);
  const [agentFilter, setAgentFilter] = useState("");
  const [eventTypeFilter, setEventTypeFilter] = useState("");
  const [searchQuery, setSearchQuery] = useState("");

  const globalFeed = useAgentViewStore((s) => s.globalFeed);
  const virtuosoRef = useRef<VirtuosoHandle>(null);
  const [atBottom, setAtBottom] = useState(true);

  // Filter the feed
  const filteredFeed = useMemo(() => {
    let result = globalFeed;

    if (agentFilter) {
      result = result.filter(
        (e) =>
          e.agent_id === agentFilter ||
          e.source_agent === agentFilter ||
          e.target_agent === agentFilter,
      );
    }

    if (eventTypeFilter) {
      result = result.filter((e) => e.event_type === eventTypeFilter);
    }

    if (searchQuery) {
      const lower = searchQuery.toLowerCase();
      result = result.filter((e) => {
        const messageType =
          (e.payload.message_type as string | undefined) ?? "";
        const payloadStr = JSON.stringify(e.payload).toLowerCase();
        return (
          messageType.toLowerCase().includes(lower) ||
          payloadStr.includes(lower)
        );
      });
    }

    return result;
  }, [globalFeed, agentFilter, eventTypeFilter, searchQuery]);

  const scrollToBottom = useCallback(() => {
    virtuosoRef.current?.scrollToIndex({
      index: "LAST",
      behavior: "smooth",
    });
  }, []);

  const itemContent = useCallback(
    (_index: number, event: AgentTelemetryEvent) => <FlowRow event={event} />,
    [],
  );

  return (
    <div
      className={`
        flex h-full shrink-0 flex-col bg-[#0d1117]
        transition-all duration-200
        w-full border-l-0
        ${collapsed
          ? "md:w-0 md:overflow-hidden md:border-l-0"
          : "md:w-72 md:border-l md:border-slate-800"
        }
      `}
    >
      {/* Collapse toggle — desktop only */}
      <button
        type="button"
        onClick={() => setCollapsed((p) => !p)}
        className="hidden md:block relative
          rounded-r bg-slate-800 px-0.5 py-2 text-slate-400 hover:bg-slate-700
          hover:text-slate-200 transition-colors"
        aria-label={collapsed ? "Expand message flow panel" : "Collapse message flow panel"}
      >
        {collapsed ? (
          <ChevronLeft className="h-4 w-4" />
        ) : (
          <ChevronRight className="h-4 w-4" />
        )}
      </button>

      {!collapsed && (
        <>
          {/* Header */}
          <div className="flex items-center justify-between border-b border-slate-800 px-3 py-2">
            <div className="flex items-center gap-2">
              <MessageSquare className="h-3.5 w-3.5 text-teal-400" />
              <span className="text-xs font-semibold text-slate-200">
                Message Flow
              </span>
              <Badge
                variant="secondary"
                className="bg-slate-700 px-1.5 text-[10px] font-mono text-slate-300"
              >
                {filteredFeed.length}
              </Badge>
            </div>
          </div>

          {/* Filters */}
          <div className="space-y-1.5 border-b border-slate-800 px-3 py-2">
            {/* Agent filter */}
            <div className="flex items-center gap-1.5">
              <Filter className="h-3 w-3 shrink-0 text-slate-500" />
              <select
                value={agentFilter}
                onChange={(e) => setAgentFilter(e.target.value)}
                className="h-6 flex-1 rounded border border-slate-700 bg-slate-900 px-1.5
                  text-[10px] text-slate-300 outline-none focus:border-slate-600"
                aria-label="Filter by agent"
              >
                <option value="">All agents</option>
                {AGENT_REGISTRY.map((a) => (
                  <option key={a.agent_id} value={a.agent_id}>
                    {a.display_name}
                  </option>
                ))}
              </select>
            </div>

            {/* Event type filter */}
            <div className="flex items-center gap-1.5">
              <Filter className="h-3 w-3 shrink-0 text-slate-500" />
              <select
                value={eventTypeFilter}
                onChange={(e) => setEventTypeFilter(e.target.value)}
                className="h-6 flex-1 rounded border border-slate-700 bg-slate-900 px-1.5
                  text-[10px] text-slate-300 outline-none focus:border-slate-600"
                aria-label="Filter by event type"
              >
                <option value="">All event types</option>
                {EVENT_TYPE_OPTIONS.map((et) => (
                  <option key={et} value={et}>
                    {et}
                  </option>
                ))}
              </select>
            </div>

            {/* Search */}
            <div className="flex items-center gap-1.5">
              <Search className="h-3 w-3 shrink-0 text-slate-500" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search messages..."
                className="h-6 flex-1 rounded border border-slate-700 bg-slate-900 px-1.5
                  text-[10px] text-slate-300 placeholder:text-slate-600
                  outline-none focus:border-slate-600"
                aria-label="Search messages by type or payload"
              />
            </div>
          </div>

          {/* Scroll to bottom button */}
          {!atBottom && filteredFeed.length > 0 && (
            <button
              type="button"
              onClick={scrollToBottom}
              className="flex items-center justify-center gap-1 border-b border-slate-800
                px-2 py-1 text-[10px] text-slate-400 hover:bg-slate-800 hover:text-slate-200
                transition-colors"
              aria-label="Scroll to latest message"
            >
              <ArrowDown className="h-3 w-3" />
              Scroll to latest
            </button>
          )}

          {/* Virtualized message list */}
          <div className="flex-1 min-h-0">
            {filteredFeed.length === 0 ? (
              <div className="flex h-full items-center justify-center text-[10px] text-slate-500">
                {globalFeed.length === 0
                  ? "No messages yet"
                  : "No messages match filters"}
              </div>
            ) : (
              <Virtuoso
                ref={virtuosoRef}
                data={filteredFeed}
                itemContent={itemContent}
                followOutput={atBottom ? "smooth" : false}
                atBottomStateChange={setAtBottom}
                atBottomThreshold={50}
                className="h-full"
              />
            )}
          </div>
        </>
      )}
    </div>
  );
}
