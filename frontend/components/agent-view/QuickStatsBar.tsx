"use client";

import { useAgentViewStore } from "@/lib/stores/agentViewStore";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatPnl(value: number): string {
  const sign = value >= 0 ? "+" : "";
  return `${sign}${value.toLocaleString("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

function formatPercent(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

// ---------------------------------------------------------------------------
// StatCell
// ---------------------------------------------------------------------------

interface StatCellProps {
  label: string;
  value: string;
  colorClass?: string;
}

function StatCell({ label, value, colorClass = "text-slate-200" }: StatCellProps) {
  return (
    <div className="flex items-center gap-2">
      <span className="text-[10px] uppercase tracking-wider text-slate-500">
        {label}
      </span>
      <span className={`font-mono text-sm tabular-nums ${colorClass}`}>
        {value}
      </span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function QuickStatsBar() {
  const stats = useAgentViewStore((s) => s.stats);

  const pnlColor =
    stats.net_pnl_session > 0
      ? "text-emerald-400"
      : stats.net_pnl_session < 0
        ? "text-red-400"
        : "text-slate-200";

  return (
    <div
      className="flex h-10 w-full items-center justify-between border-t border-slate-800 bg-[#0d1117] px-4"
      role="contentinfo"
      aria-label="Quick trading statistics"
    >
      <div className="flex items-center gap-6">
        <StatCell
          label="Orders"
          value={stats.total_orders_session.toLocaleString()}
        />
        <StatCell
          label="Fills"
          value={stats.total_fills_session.toLocaleString()}
        />
        <StatCell
          label="Win Rate"
          value={formatPercent(stats.win_rate_session)}
        />
        <StatCell
          label="Net PnL"
          value={formatPnl(stats.net_pnl_session)}
          colorClass={pnlColor}
        />
        <StatCell
          label="Drawdown"
          value={formatPercent(stats.largest_drawdown_session)}
          colorClass="text-amber-400"
        />
        <StatCell
          label="Positions"
          value={String(stats.active_positions)}
        />
        <StatCell
          label="Pending"
          value={String(stats.pending_orders)}
        />
      </div>
    </div>
  );
}
