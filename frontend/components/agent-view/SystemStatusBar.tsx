"use client";

import { useEffect, useState } from "react";
import { Activity, Clock } from "lucide-react";
import { useAgentViewStore } from "@/lib/stores/agentViewStore";
import { SlowModeControl } from "./SlowModeControl";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type SystemState = "LIVE" | "PAPER" | "PAUSED" | "ERROR";

interface SlowModeProps {
  enabled: boolean;
  rateMs: number;
  bufferedCount: number;
  toggle: () => void;
  setRate: (ms: number) => void;
  flushNow: () => void;
}

interface SystemStatusBarProps {
  slowMode: SlowModeProps;
  systemState?: SystemState;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const STATE_STYLES: Record<SystemState, string> = {
  LIVE: "bg-emerald-500/20 text-emerald-400 border-emerald-500/30",
  PAPER: "bg-amber-500/20 text-amber-400 border-amber-500/30",
  PAUSED: "bg-slate-500/20 text-slate-400 border-slate-500/30",
  ERROR: "bg-red-500/20 text-red-400 border-red-500/30",
};

function formatTime(date: Date): { utc: string; local: string } {
  const pad2 = (n: number) => String(n).padStart(2, "0");
  const pad3 = (n: number) => String(n).padStart(3, "0");

  const utc = `${pad2(date.getUTCHours())}:${pad2(date.getUTCMinutes())}:${pad2(date.getUTCSeconds())}.${pad3(date.getUTCMilliseconds())}`;
  const local = `${pad2(date.getHours())}:${pad2(date.getMinutes())}:${pad2(date.getSeconds())}.${pad3(date.getMilliseconds())}`;

  return { utc, local };
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function SystemStatusBar({
  slowMode,
  systemState = "PAPER",
}: SystemStatusBarProps) {
  const stats = useAgentViewStore((s) => s.stats);
  const [now, setNow] = useState(() => new Date());

  // High-frequency clock update
  useEffect(() => {
    const timer = setInterval(() => setNow(new Date()), 100);
    return () => clearInterval(timer);
  }, []);

  const time = formatTime(now);
  const { agent_health_summary: health } = stats;
  const totalAgents =
    health.healthy + health.degraded + health.error + health.offline;

  return (
    <div
      className="flex h-10 w-full items-center justify-between border-b border-slate-800 bg-[#0d1117] px-2 md:px-4"
      role="banner"
      aria-label="System status bar"
    >
      {/* Left section: State + Clock */}
      <div className="flex items-center gap-2 md:gap-4">
        {/* System state pill */}
        <span
          className={`rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider ${STATE_STYLES[systemState]}`}
        >
          {systemState}
        </span>

        {/* Health — always visible, condensed on mobile */}
        <div className="flex items-center gap-1 text-xs">
          <span className="font-mono text-emerald-400">{health.healthy}</span>
          <span className="text-slate-600">/</span>
          <span className="font-mono text-slate-300">{totalAgents}</span>
          <span className="hidden sm:inline text-slate-500">healthy</span>
          {health.degraded > 0 && (
            <>
              <span className="text-slate-700">|</span>
              <span className="font-mono text-amber-400">
                {health.degraded}
              </span>
              <span className="hidden sm:inline text-slate-500">degraded</span>
            </>
          )}
          {health.error > 0 && (
            <>
              <span className="text-slate-700">|</span>
              <span className="font-mono text-red-400">{health.error}</span>
              <span className="hidden sm:inline text-slate-500">error</span>
            </>
          )}
        </div>
      </div>

      {/* Center section: Clock + Throughput — clock hidden on mobile */}
      <div className="flex items-center gap-2 md:gap-4">
        {/* System clock — hidden on small screens */}
        <div className="hidden md:flex items-center gap-1.5 text-xs">
          <Clock className="h-3 w-3 text-slate-500" />
          <span className="font-mono tabular-nums text-slate-300">
            {time.utc}
          </span>
          <span className="text-slate-600">UTC</span>
          <span className="text-slate-700">|</span>
          <span className="font-mono tabular-nums text-slate-400">
            {time.local}
          </span>
          <span className="text-slate-600">Local</span>
        </div>

        {/* Message throughput — always visible */}
        <div className="flex items-center gap-1 text-xs">
          <Activity className="h-3 w-3 text-slate-500" />
          <span className="font-mono tabular-nums text-slate-300">
            {stats.messages_per_second.toFixed(1)}
          </span>
          <span className="hidden sm:inline text-slate-500">msgs/sec</span>
        </div>
      </div>

      {/* Right section: Slow Mode — hidden on mobile (available in Stats tab) */}
      <div className="hidden md:block">
        <SlowModeControl {...slowMode} />
      </div>
    </div>
  );
}
