"use client";

import { Bot } from "lucide-react";
import { cn } from "@/lib/utils";
import { AgentAvatar, type AgentKind } from "@/components/agentic/AgentAvatar";
import { StatusDot } from "@/components/data-display";
import type { AgentInfo } from "@/lib/types/telemetry";

/**
 * Left-rail Agent Roster (220px) per surface spec §2.
 *
 * Each entry: AgentAvatar + name + StatusDot + last-emit time. Click toggles
 * the "include this agent" filter (mirrors center-column multi-select).
 * Right-click would open silence/dashboard/canvas actions per spec — not yet
 * wired (Pending).
 */

export const ROSTER_KINDS: AgentKind[] = [
  "ta",
  "regime",
  "sentiment",
  "slm",
  "debate",
  "analyst",
];

export const KIND_TO_BACKEND: Record<AgentKind, string> = {
  ta: "ta_agent",
  regime: "regime_hmm",
  sentiment: "sentiment",
  slm: "slm_inference",
  debate: "debate",
  analyst: "analyst",
};

const KIND_LABELS: Record<AgentKind, string> = {
  ta: "ta_agent",
  regime: "regime_hmm",
  sentiment: "sentiment",
  slm: "slm_inference",
  debate: "debate",
  analyst: "analyst",
};

type StatusDotState = "live" | "idle" | "error";

function statusForAgent(info: AgentInfo | undefined): StatusDotState {
  if (!info) return "idle";
  if (info.health === "error" || info.health === "offline") return "error";
  if (info.health === "degraded") return "idle";
  if (!info.last_active) return "idle";
  const recentMs = Date.now() - new Date(info.last_active).getTime();
  if (Number.isNaN(recentMs)) return "idle";
  if (recentMs < 5 * 60_000) return "live";
  return "idle";
}

function formatRelative(ts: string | undefined): string {
  if (!ts) return "—";
  const ms = Date.now() - new Date(ts).getTime();
  if (!Number.isFinite(ms) || ms < 0) return "—";
  const sec = Math.floor(ms / 1000);
  if (sec < 60) return `${sec}s`;
  const min = Math.floor(sec / 60);
  if (min < 60) return `${min}m`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `${hr}h`;
  return `${Math.floor(hr / 24)}d`;
}

interface RosterProps {
  agents: Record<string, AgentInfo>;
  enabled: Set<AgentKind>;
  onToggle: (kind: AgentKind) => void;
}

export function Roster({ agents, enabled, onToggle }: RosterProps) {
  return (
    <aside
      className="w-56 shrink-0 border-r border-border-subtle bg-bg-panel flex flex-col"
      aria-label="Agent roster"
    >
      <header className="flex items-center gap-2 px-3 h-9 border-b border-border-subtle">
        <Bot className="w-3.5 h-3.5 text-fg-muted" strokeWidth={1.5} aria-hidden />
        <span className="text-[10px] uppercase tracking-wider text-fg-muted num-tabular">
          roster
        </span>
      </header>
      <ul className="flex-1 overflow-y-auto py-1">
        {ROSTER_KINDS.map((kind) => {
          const backendId = KIND_TO_BACKEND[kind];
          const info = agents[backendId];
          const state = statusForAgent(info);
          const isOn = enabled.has(kind);
          return (
            <li key={kind}>
              <button
                type="button"
                onClick={() => onToggle(kind)}
                aria-pressed={isOn}
                className={cn(
                  "w-full flex items-center gap-2 px-3 h-10 text-left transition-colors",
                  "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent-500",
                  isOn
                    ? "bg-bg-rowhover text-fg"
                    : "text-fg-muted hover:bg-bg-rowhover/60 hover:text-fg"
                )}
              >
                <AgentAvatar kind={kind} size="sm" />
                <div className="flex-1 min-w-0">
                  <div className="text-[12px] font-medium num-tabular truncate">
                    {KIND_LABELS[kind]}
                  </div>
                  <div className="text-[10px] text-fg-muted num-tabular flex items-center gap-1">
                    <StatusDot state={state} size={6} pulse={state === "live"} />
                    {info ? formatRelative(info.last_active) : "no telemetry"}
                  </div>
                </div>
              </button>
            </li>
          );
        })}
      </ul>
    </aside>
  );
}
