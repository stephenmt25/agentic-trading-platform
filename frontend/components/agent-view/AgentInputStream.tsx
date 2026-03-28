"use client";

import { useCallback, useRef, useState, useMemo } from "react";
import { Virtuoso, type VirtuosoHandle } from "react-virtuoso";
import { ArrowDown, Radio } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { useAgentViewStore } from "@/lib/stores/agentViewStore";
import { AGENT_TYPE_COLORS, AGENT_REGISTRY } from "@/lib/constants/agent-view";
import type { AgentTelemetryEvent, AgentType } from "@/lib/types/telemetry";

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

function truncate(value: unknown, maxLen: number): string {
  const str =
    typeof value === "string" ? value : JSON.stringify(value) ?? "";
  return str.length > maxLen ? str.slice(0, maxLen) + "\u2026" : str;
}

function resolveAgentType(agentId: string): AgentType | undefined {
  return AGENT_REGISTRY.find((a) => a.agent_id === agentId)?.agent_type;
}

// ---------------------------------------------------------------------------
// Row Component
// ---------------------------------------------------------------------------

interface StreamRowProps {
  event: AgentTelemetryEvent;
  isNew: boolean;
}

function StreamRow({ event, isNew }: StreamRowProps) {
  const [expanded, setExpanded] = useState(false);
  const sourceType = event.source_agent
    ? resolveAgentType(event.source_agent)
    : undefined;
  const sourceColor = sourceType
    ? AGENT_TYPE_COLORS[sourceType]
    : "#94a3b8";

  const messageType =
    (event.payload.message_type as string | undefined) ??
    event.event_type;

  return (
    <div
      className={`
        group border-b border-slate-800/50 px-3 py-1.5 text-xs
        odd:bg-slate-900/30
        ${isNew ? "animate-pulse" : ""}
      `}
      style={{ animationDuration: "500ms", animationIterationCount: 1 }}
    >
      <div className="flex items-center gap-3">
        {/* Timestamp */}
        <span className="shrink-0 font-mono text-slate-500">
          {formatTimestamp(event.timestamp)}
        </span>

        {/* Source agent */}
        <span
          className="shrink-0 font-mono text-[11px] font-medium"
          style={{ color: sourceColor }}
        >
          {event.source_agent ?? "system"}
        </span>

        {/* Message type */}
        <span className="shrink-0 rounded bg-slate-800 px-1.5 py-0.5 font-mono text-[10px] text-slate-300">
          {messageType}
        </span>

        {/* Payload summary */}
        <button
          type="button"
          onClick={() => setExpanded((p) => !p)}
          className="min-w-0 truncate text-left font-mono text-slate-400 hover:text-slate-200 transition-colors"
          aria-label={expanded ? "Collapse payload" : "Expand payload"}
        >
          {truncate(event.payload, 80)}
        </button>
      </div>

      {expanded && (
        <pre className="mt-1.5 max-h-48 overflow-auto rounded bg-slate-950 p-2 font-mono text-[10px] text-slate-300">
          {JSON.stringify(event.payload, null, 2)}
        </pre>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface AgentInputStreamProps {
  agentId: string;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function AgentInputStream({ agentId }: AgentInputStreamProps) {
  const allEvents = useAgentViewStore((s) => s.agentEvents[agentId]);
  const inputEvents = useMemo(
    () => (allEvents ?? []).filter((e) => e.event_type === "input_received"),
    [allEvents],
  );

  const virtuosoRef = useRef<VirtuosoHandle>(null);
  const [atBottom, setAtBottom] = useState(true);

  const scrollToBottom = useCallback(() => {
    virtuosoRef.current?.scrollToIndex({
      index: "LAST",
      behavior: "smooth",
    });
  }, []);

  const itemContent = useCallback(
    (_index: number, event: AgentTelemetryEvent) => (
      <StreamRow event={event} isNew={false} />
    ),
    [],
  );

  return (
    <div className="flex h-full flex-col bg-[#161b22]">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-slate-800 px-3 py-2">
        <div className="flex items-center gap-2">
          <Radio className="h-3.5 w-3.5 text-emerald-400" />
          <span className="text-xs font-semibold text-slate-200">
            Input Stream
          </span>
          <Badge
            variant="secondary"
            className="bg-slate-700 px-1.5 text-[10px] font-mono text-slate-300"
          >
            {inputEvents.length}
          </Badge>
        </div>

        {!atBottom && (
          <button
            type="button"
            onClick={scrollToBottom}
            className="flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px] text-slate-400 hover:bg-slate-700 hover:text-slate-200 transition-colors"
            aria-label="Scroll to latest"
          >
            <ArrowDown className="h-3 w-3" />
            Latest
          </button>
        )}
      </div>

      {/* Virtualized list */}
      <div className="flex-1 min-h-0">
        {inputEvents.length === 0 ? (
          <div className="flex h-full items-center justify-center text-xs text-slate-500">
            No input events received
          </div>
        ) : (
          <Virtuoso
            ref={virtuosoRef}
            data={inputEvents}
            itemContent={itemContent}
            followOutput={atBottom ? "smooth" : false}
            atBottomStateChange={setAtBottom}
            atBottomThreshold={50}
            className="h-full"
          />
        )}
      </div>
    </div>
  );
}
