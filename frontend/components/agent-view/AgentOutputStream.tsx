"use client";

import { useCallback, useMemo, useRef, useState } from "react";
import { Virtuoso, type VirtuosoHandle } from "react-virtuoso";
import { ArrowDown, Send } from "lucide-react";
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

/** Detect order/execution events for accent highlighting. */
function isOrderEvent(event: AgentTelemetryEvent): boolean {
  const messageType =
    (event.payload.message_type as string | undefined) ?? "";
  const keywords = ["order", "execution", "fill", "trade", "cancel"];
  const lower = messageType.toLowerCase();
  return keywords.some((kw) => lower.includes(kw));
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
  const targetType = event.target_agent
    ? resolveAgentType(event.target_agent)
    : undefined;
  const targetColor = targetType
    ? AGENT_TYPE_COLORS[targetType]
    : "#94a3b8";

  const messageType =
    (event.payload.message_type as string | undefined) ??
    event.event_type;

  const isOrder = isOrderEvent(event);

  return (
    <div
      className={`
        group border-b border-slate-800/50 px-3 py-1.5 text-xs
        odd:bg-slate-900/30
        ${isNew ? "animate-pulse" : ""}
      `}
      style={{
        animationDuration: "500ms",
        animationIterationCount: 1,
        borderLeftWidth: isOrder ? "3px" : undefined,
        borderLeftColor: isOrder ? "#60a5fa" : undefined,
      }}
    >
      <div className="flex items-center gap-3">
        {/* Timestamp */}
        <span className="shrink-0 font-mono text-slate-500">
          {formatTimestamp(event.timestamp)}
        </span>

        {/* Target agent */}
        <span
          className="shrink-0 font-mono text-[11px] font-medium"
          style={{ color: targetColor }}
        >
          {event.target_agent ?? "broadcast"}
        </span>

        {/* Message type */}
        <span
          className={`
            shrink-0 rounded px-1.5 py-0.5 font-mono text-[10px]
            ${isOrder ? "bg-blue-500/20 text-blue-300" : "bg-slate-800 text-slate-300"}
          `}
        >
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

interface AgentOutputStreamProps {
  agentId: string;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function AgentOutputStream({ agentId }: AgentOutputStreamProps) {
  const allEvents = useAgentViewStore((s) => s.agentEvents[agentId]);
  const outputEvents = useMemo(
    () => (allEvents ?? []).filter((e) => e.event_type === "output_emitted"),
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
          <Send className="h-3.5 w-3.5 text-blue-400" />
          <span className="text-xs font-semibold text-slate-200">
            Output Stream
          </span>
          <Badge
            variant="secondary"
            className="bg-slate-700 px-1.5 text-[10px] font-mono text-slate-300"
          >
            {outputEvents.length}
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
        {outputEvents.length === 0 ? (
          <div className="flex h-full items-center justify-center text-xs text-slate-500">
            No output events emitted
          </div>
        ) : (
          <Virtuoso
            ref={virtuosoRef}
            data={outputEvents}
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
