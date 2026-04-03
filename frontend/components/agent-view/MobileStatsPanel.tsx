"use client";

import { useAgentViewStore } from "@/lib/stores/agentViewStore";
import { SlowModeControl } from "./SlowModeControl";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface SlowModeProps {
  enabled: boolean;
  rateMs: number;
  bufferedCount: number;
  toggle: () => void;
  setRate: (ms: number) => void;
  flushNow: () => void;
}

interface MobileStatsPanelProps {
  slowMode: SlowModeProps;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatPnl(value: number): string {
  const sign = value >= 0 ? "+" : "";
  return `${sign}$${Math.abs(value).toLocaleString("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

function formatPercent(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

// ---------------------------------------------------------------------------
// StatCard
// ---------------------------------------------------------------------------

interface StatCardProps {
  label: string;
  value: string;
  colorClass?: string;
}

function StatCard({ label, value, colorClass = "text-slate-100" }: StatCardProps) {
  return (
    <div className="flex flex-col gap-1 rounded-lg bg-[#161b22] p-4">
      <span className="text-[11px] font-medium uppercase tracking-wider text-slate-500">
        {label}
      </span>
      <span className={`font-mono text-2xl font-semibold tabular-nums ${colorClass}`}>
        {value}
      </span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function MobileStatsPanel({ slowMode }: MobileStatsPanelProps) {
  const stats = useAgentViewStore((s) => s.stats);

  const pnlColor =
    stats.net_pnl_session > 0
      ? "text-emerald-400"
      : stats.net_pnl_session < 0
        ? "text-red-400"
        : "text-slate-100";

  return (
    <div className="flex h-full flex-col overflow-y-auto bg-[#0d1117] px-4 py-4">
      {/* Header */}
      <div className="mb-4">
        <span className="text-[10px] font-medium uppercase tracking-wider text-slate-500">
          System Overview
        </span>
        <h2 className="text-lg font-semibold text-slate-100">Trading Stats</h2>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-2 gap-3">
        <StatCard
          label="Orders"
          value={stats.total_orders_session.toLocaleString()}
        />
        <StatCard
          label="Fills"
          value={stats.total_fills_session.toLocaleString()}
        />
        <StatCard
          label="Win Rate"
          value={formatPercent(stats.win_rate_session)}
          colorClass="text-emerald-400"
        />
        <StatCard
          label="Net PnL"
          value={formatPnl(stats.net_pnl_session)}
          colorClass={pnlColor}
        />
        <StatCard
          label="Drawdown"
          value={formatPercent(stats.largest_drawdown_session)}
          colorClass="text-amber-400"
        />
        <StatCard
          label="Positions"
          value={String(stats.active_positions)}
        />
        <StatCard
          label="Pending"
          value={String(stats.pending_orders)}
        />
        <StatCard
          label="Msgs/sec"
          value={stats.messages_per_second.toFixed(1)}
          colorClass="text-blue-400"
        />
      </div>

      {/* Slow Mode Controls */}
      <div className="mt-6 rounded-lg bg-[#161b22] p-4">
        <h3 className="mb-3 text-xs font-semibold text-slate-200">
          Slow Mode
        </h3>
        <SlowModeControl {...slowMode} />
      </div>
    </div>
  );
}
