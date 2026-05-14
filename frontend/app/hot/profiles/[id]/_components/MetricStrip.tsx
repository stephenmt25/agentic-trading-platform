"use client";

import { cn } from "@/lib/utils";

export interface ProfileStrip {
  net_pnl_since_boot: number;
  trades_today: number;
  win_rate_today: number | null;
  drawdown_pct: number;
  allocation_pct: number;
  max_allocation_pct: number;
}

interface CardSpec {
  label: string;
  value: string;
  tone?: "ok" | "danger" | "warn" | "neutral";
  hint?: string;
}

function buildCards(s: ProfileStrip): CardSpec[] {
  const pnlPositive = s.net_pnl_since_boot >= 0;
  const pnlStr =
    (pnlPositive ? "+" : "") +
    s.net_pnl_since_boot.toLocaleString(undefined, {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    });

  const allocRatio =
    s.max_allocation_pct > 0 ? s.allocation_pct / s.max_allocation_pct : 0;
  const allocTone: CardSpec["tone"] =
    allocRatio >= 1 ? "danger" : allocRatio >= 0.85 ? "warn" : "neutral";

  const ddTone: CardSpec["tone"] =
    s.drawdown_pct >= 0.05
      ? "danger"
      : s.drawdown_pct >= 0.025
        ? "warn"
        : "neutral";

  return [
    {
      label: "Net P&L since boot",
      value: pnlStr,
      tone: pnlPositive ? (s.net_pnl_since_boot > 0 ? "ok" : "neutral") : "danger",
    },
    {
      label: "Trades today",
      value: s.trades_today.toLocaleString(),
    },
    {
      label: "Win rate today",
      value:
        s.win_rate_today === null
          ? "—"
          : `${(s.win_rate_today * 100).toFixed(1)}%`,
      hint: s.win_rate_today === null ? "no closed trades today" : undefined,
    },
    {
      label: "Drawdown",
      value:
        s.drawdown_pct === 0
          ? "0.00%"
          : `-${(s.drawdown_pct * 100).toFixed(2)}%`,
      tone: ddTone,
    },
    {
      label: "Allocation",
      value: `${(s.allocation_pct * 100).toFixed(1)}% / ${(s.max_allocation_pct * 100).toFixed(0)}%`,
      tone: allocTone,
    },
  ];
}

export function MetricStrip({ strip }: { strip: ProfileStrip | null }) {
  if (!strip) {
    return (
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-2">
        {[0, 1, 2, 3, 4].map((i) => (
          <div
            key={i}
            className="rounded-md border border-border-subtle bg-bg-panel/50 h-[68px] animate-pulse"
          />
        ))}
      </div>
    );
  }

  const cards = buildCards(strip);
  return (
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-2">
      {cards.map((c) => (
        <MetricCard key={c.label} {...c} />
      ))}
    </div>
  );
}

function MetricCard({ label, value, tone = "neutral", hint }: CardSpec) {
  return (
    <div
      className={cn(
        "rounded-md border bg-bg-panel px-3 py-2.5 flex flex-col gap-1",
        tone === "danger"
          ? "border-danger-700/40"
          : tone === "warn"
            ? "border-warn-700/40"
            : "border-border-subtle"
      )}
    >
      <p className="text-[10px] uppercase tracking-wider text-fg-muted">
        {label}
      </p>
      <p
        className={cn(
          "text-[18px] font-semibold tracking-tight num-tabular leading-none",
          tone === "ok" && "text-bid-300",
          tone === "danger" && "text-danger-500",
          tone === "warn" && "text-warn-400",
          tone === "neutral" && "text-fg"
        )}
        title={hint}
      >
        {value}
      </p>
    </div>
  );
}
