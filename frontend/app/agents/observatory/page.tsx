"use client";

import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { Bot, Search, X } from "lucide-react";
import { Virtuoso, type VirtuosoHandle } from "react-virtuoso";

import { Button, Input, Select, Tag } from "@/components/primitives";
import { Pill, StatusDot } from "@/components/data-display";
import { AgentTrace } from "@/components/agentic";
import type { AgentKind } from "@/components/agentic/AgentAvatar";
import { useAgentViewStore } from "@/lib/stores/agentViewStore";
import { useConnectionStore } from "@/lib/stores/connectionStore";
import type { AgentTelemetryEvent } from "@/lib/types/telemetry";

import { Roster, ROSTER_KINDS, KIND_TO_BACKEND } from "./_components/Roster";
import { FocusPanel } from "./_components/FocusPanel";
import { backendIdToKind } from "./_components/eventHelpers";

/**
 * /agents/observatory — Agent Observatory.
 * Surface spec: docs/design/05-surface-specs/02-agent-observatory.md.
 *
 * Three-column COOL surface: roster (220px) | event stream (flex) | focus
 * panel (460px). Events stream in via the existing wsClient → agentViewStore;
 * we read globalFeed as a virtualized list and filter client-side.
 *
 * Backend gaps surfaced as warn Tags per the "render structure, never fake"
 * pattern:
 *   - Free-text search across reasoning bodies (telemetry doesn't index).
 *   - Symbol filter (events don't carry a normalized symbol field).
 *   - Override / silence / replay actions (intervention API not exposed).
 *   - DebatePanel content (no debate event_type emitted by backend).
 */

const TIME_RANGE_OPTIONS = [
  { value: "5m", label: "Last 5 min" },
  { value: "15m", label: "Last 15 min" },
  { value: "1h", label: "Last 1 hour" },
  { value: "all", label: "All buffered" },
];

const TIME_RANGE_MS: Record<string, number | null> = {
  "5m": 5 * 60_000,
  "15m": 15 * 60_000,
  "1h": 60 * 60_000,
  all: null,
};

export default function AgentObservatoryPage() {
  const agents = useAgentViewStore((s) => s.agents);
  const globalFeed = useAgentViewStore((s) => s.globalFeed);
  const wsConnected = useConnectionStore((s) => s.backendStatus) === "connected";

  const [enabled, setEnabled] = useState<Set<AgentKind>>(
    () => new Set(ROSTER_KINDS)
  );
  const [timeRange, setTimeRange] = useState<string>("1h");
  const [search, setSearch] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(null);

  // Periodic clock tick so the time-range filter and roster relative times
  // refresh on their own. Keeps Date.now() out of render — the lint rule
  // (react-hooks/purity) flags Date.now() inside useMemo.
  const [nowTick, setNowTick] = useState(() => Date.now());
  useEffect(() => {
    const id = window.setInterval(() => setNowTick(Date.now()), 5_000);
    return () => window.clearInterval(id);
  }, []);

  const toggleAgent = useCallback((kind: AgentKind) => {
    setEnabled((prev) => {
      const next = new Set(prev);
      if (next.has(kind)) next.delete(kind);
      else next.add(kind);
      return next;
    });
  }, []);

  // Filter the global feed to: known agentic kinds × enabled set × time
  // window × free-text title search (event_type / agent_id / quick payload
  // string match).
  const filtered = useMemo(() => {
    const enabledBackend = new Set<string>();
    for (const k of enabled) enabledBackend.add(KIND_TO_BACKEND[k]);
    const cutoff =
      TIME_RANGE_MS[timeRange] === null
        ? 0
        : nowTick - (TIME_RANGE_MS[timeRange] ?? 0);
    const q = search.trim().toLowerCase();
    return globalFeed
      .filter((e) => enabledBackend.has(e.agent_id))
      .filter((e) => {
        if (!cutoff) return true;
        const t = new Date(e.timestamp).getTime();
        return Number.isFinite(t) ? t >= cutoff : true;
      })
      .filter((e) => {
        if (!q) return true;
        return (
          e.agent_id.toLowerCase().includes(q) ||
          e.event_type.toLowerCase().includes(q)
        );
      });
  }, [globalFeed, enabled, timeRange, search, nowTick]);

  // Newest-first for visual order (the store appends newest at end).
  const ordered = useMemo(() => filtered.slice().reverse(), [filtered]);

  const selectedEvent = useMemo(
    () => ordered.find((e) => e.id === selectedId) ?? null,
    [ordered, selectedId]
  );

  // ---------- Keyboard navigation ----------
  const listRef = useRef<VirtuosoHandle | null>(null);
  const [activeIndex, setActiveIndex] = useState(0);
  // Derive the safe index instead of clamping in an effect — keeps render
  // pure (the linter flags setState-in-effect).
  const safeActiveIndex = useMemo(
    () => Math.min(activeIndex, Math.max(0, ordered.length - 1)),
    [activeIndex, ordered.length]
  );

  const focusIndex = useCallback(
    (idx: number) => {
      if (idx < 0 || idx >= ordered.length) return;
      setActiveIndex(idx);
      listRef.current?.scrollToIndex({
        index: idx,
        align: "center",
        behavior: "smooth",
      });
    },
    [ordered.length]
  );

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement).tagName?.toLowerCase();
      if (tag === "input" || tag === "textarea") return;
      if (e.metaKey || e.ctrlKey) {
        // Cmd+1..6 toggles agents (per spec §7).
        const n = Number(e.key);
        if (n >= 1 && n <= ROSTER_KINDS.length) {
          e.preventDefault();
          toggleAgent(ROSTER_KINDS[n - 1]);
        }
        return;
      }
      if (e.key === "j") {
        e.preventDefault();
        focusIndex(safeActiveIndex + 1);
      } else if (e.key === "k") {
        e.preventDefault();
        focusIndex(safeActiveIndex - 1);
      } else if (e.key === "Enter") {
        const evt = ordered[safeActiveIndex];
        if (evt) setSelectedId(evt.id);
      } else if (e.key === "f" || e.key === "F") {
        const el = document.getElementById("observatory-search");
        if (el && document.activeElement !== el) {
          e.preventDefault();
          (el as HTMLInputElement).focus();
        }
      } else if (e.key === "Escape") {
        setSelectedId(null);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [safeActiveIndex, ordered, focusIndex, toggleAgent]);

  return (
    <div data-mode="cool" className="flex flex-col h-full bg-bg-canvas text-fg">
      {/* Top header */}
      <header className="flex items-center justify-between gap-4 border-b border-border-subtle px-6 py-3">
        <div className="flex items-center gap-2 text-[12px] text-fg-muted">
          <Bot className="w-3.5 h-3.5" strokeWidth={1.5} aria-hidden />
          <span className="num-tabular">Agent Observatory</span>
          <Pill
            intent={wsConnected ? "bid" : "neutral"}
            icon={
              <StatusDot
                state={wsConnected ? "live" : "idle"}
                size={6}
                pulse={wsConnected}
              />
            }
          >
            {wsConnected ? "Live" : "Disconnected"}
          </Pill>
        </div>
        <div className="flex items-center gap-2">
          <Tag intent="warn">Pending overrides</Tag>
        </div>
      </header>

      <div className="flex-1 min-h-0 flex overflow-hidden">
        {/* Left rail */}
        <Roster agents={agents} enabled={enabled} onToggle={toggleAgent} />

        {/* Center: filter bar + event stream */}
        <section className="flex-1 min-w-0 flex flex-col overflow-hidden">
          {/* Filter bar */}
          <div className="flex items-center gap-2 px-4 h-12 border-b border-border-subtle bg-bg-panel">
            <div className="relative flex-1 max-w-md">
              <Input
                id="observatory-search"
                placeholder="Filter by agent or event type"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                density="compact"
                leftAdornment={
                  <Search className="w-3.5 h-3.5" strokeWidth={1.5} />
                }
                aria-label="Search events"
              />
              {search && (
                <button
                  type="button"
                  onClick={() => setSearch("")}
                  aria-label="Clear search"
                  className="absolute right-2 top-1/2 -translate-y-1/2 text-fg-muted hover:text-fg"
                >
                  <X className="w-3 h-3" strokeWidth={1.5} aria-hidden />
                </button>
              )}
            </div>

            <Select
              options={TIME_RANGE_OPTIONS}
              value={timeRange}
              onValueChange={(v) => setTimeRange(v)}
              density="compact"
              aria-label="Time range"
              className="w-40"
            />

            <span className="ml-auto inline-flex items-center gap-2 text-[11px] text-fg-muted">
              <Tag intent="warn">Pending</Tag>
              <span>symbol filter · reasoning-body search</span>
            </span>
          </div>

          {/* Event stream */}
          <div className="flex-1 min-h-0 relative">
            {ordered.length === 0 ? (
              <EmptyStream
                hasFilters={
                  search.length > 0 ||
                  enabled.size < ROSTER_KINDS.length ||
                  timeRange !== "all"
                }
                onClear={() => {
                  setSearch("");
                  setEnabled(new Set(ROSTER_KINDS));
                  setTimeRange("all");
                }}
              />
            ) : (
              <Virtuoso
                ref={listRef}
                className="h-full"
                data={ordered}
                computeItemKey={(_, evt) => evt.id}
                itemContent={(idx, evt) => (
                  <EventRow
                    event={evt}
                    active={idx === safeActiveIndex}
                    selected={evt.id === selectedId}
                    onSelect={() => {
                      setSelectedId(evt.id);
                      setActiveIndex(idx);
                    }}
                  />
                )}
              />
            )}
          </div>
        </section>

        {/* Right: focus panel */}
        <FocusPanel
          selectedEvent={selectedEvent}
          agents={agents}
          recentEvents={filtered}
        />
      </div>
    </div>
  );
}

/* ----------------------------- Stream row -------------------------------- */

interface EventRowProps {
  event: AgentTelemetryEvent;
  active: boolean;
  selected: boolean;
  onSelect: () => void;
}

function EventRow({ event, active, selected, onSelect }: EventRowProps) {
  const kind = backendIdToKind(event.agent_id);
  if (!kind) return null;

  const payload = event.payload ?? {};
  const inputs = payload.inputs as Record<string, unknown> | undefined;
  const output = payload.output as Record<string, unknown> | undefined;
  const reasoning = payload.reasoning as string | undefined;

  const state =
    event.event_type === "error"
      ? "errored"
      : event.event_type === "decision_trace"
        ? "complete"
        : "complete";

  return (
    <div
      data-active={active || undefined}
      data-selected={selected || undefined}
      className="px-4 py-2"
    >
      <button
        type="button"
        onClick={onSelect}
        className="block w-full text-left focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent-500 rounded-md"
        aria-pressed={selected}
      >
        <AgentTrace
          agent={kind}
          emittedAt={new Date(event.timestamp).getTime()}
          state={state as "complete" | "errored"}
          density="compact"
          input={
            inputs ? (
              <pre className="font-mono text-[11px] text-fg-secondary whitespace-pre-wrap break-words max-h-24 overflow-hidden">
                {JSON.stringify(inputs, null, 2)}
              </pre>
            ) : undefined
          }
          reasoning={
            reasoning ? (
              <p className="text-[12px] text-fg-secondary truncate">
                {reasoning}
              </p>
            ) : undefined
          }
          output={
            output ? (
              <pre className="font-mono text-[11px] text-fg-secondary whitespace-pre-wrap break-words max-h-24 overflow-hidden">
                {JSON.stringify(output, null, 2)}
              </pre>
            ) : (
              <span className="font-mono text-[11px] text-fg-muted">
                {event.event_type}
              </span>
            )
          }
          error={
            event.event_type === "error"
              ? (payload.error as string | undefined) ?? "error"
              : undefined
          }
          className={selected ? "ring-2 ring-accent-500/40" : undefined}
        />
      </button>
    </div>
  );
}

/* ----------------------------- Empty state -------------------------------- */

function EmptyStream({
  hasFilters,
  onClear,
}: {
  hasFilters: boolean;
  onClear: () => void;
}) {
  return (
    <div className="absolute inset-0 flex items-center justify-center p-6">
      <div className="rounded-md border border-border-subtle bg-bg-panel p-6 max-w-sm flex flex-col gap-3 items-start">
        {hasFilters ? (
          <>
            <p className="text-[13px] text-fg">No events match these filters.</p>
            <Button intent="secondary" size="sm" onClick={onClear}>
              Clear filters
            </Button>
          </>
        ) : (
          <>
            <p className="text-[13px] text-fg">
              No agent emissions yet in this session.
            </p>
            <p className="text-[11px] text-fg-muted">
              Telemetry streams in via WebSocket on{" "}
              <span className="font-mono">pubsub:agent_telemetry</span>. If
              your profile is paused or agents idle, this view stays empty.
            </p>
          </>
        )}
      </div>
    </div>
  );
}
